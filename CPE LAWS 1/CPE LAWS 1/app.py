# D:/school/CPE LAWS/app.py
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import datetime
import json
import csv
from io import StringIO
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_fallback_key_in_case_env_is_missing')
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compliance_system.db')

# --- DSR Proof Upload Configuration ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'uploads')
ALLOWED_PROOF_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp'}
MAX_PROOF_SIZE = 5 * 1024 * 1024  # 5 MB
DSR_TYPES = ['Access', 'Rectification', 'Erasure', 'Restriction', 'Portability', 'Objection']

# Ensure the upload folder exists (relative to this project's instance directory)
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    pass

# --- Database Setup ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def _serialize_row(row):
    """Helper to convert a sqlite3.Row object to a dict, formatting dates."""
    d = dict(row)
    for key, value in d.items():
        if isinstance(value, datetime.datetime):
            d[key] = value.isoformat() + "Z" # Add Z for UTC
    return d

# --- Audit Logging ---
# This function is registered once before the first request.
@app.after_request
def perform_audit_log(response):
    # Check if there's a log function queued up on the g object
    if hasattr(g, 'audit_log_function'):
        g.audit_log_function(response)
    return response

def audit_log(action_type, description_template):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Defer the logging action by attaching it to the g object
            def log_action(response):
                # We only log if the request was successful (status code 2xx or 3xx)
                if not (200 <= response.status_code < 400):
                    return

                try:
                    db = get_db()
                    if 'user_id' in session:
                        user = db.execute('SELECT name, role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
                        user_identity = f"{user['name']} ({user['role']})" if user else "Unknown User"

                        # Combine all possible formatting sources
                        format_args = {**kwargs, **request.view_args, **request.form}

                        description = description_template.format(**format_args)
                        json_payload = request.get_json(silent=True) or request.form

                        db.execute(
                            'INSERT INTO audit_logs (user_identity, action_type, source_ip, description, json_payload) VALUES (?, ?, ?, ?, ?)',
                            (user_identity, action_type, request.remote_addr, description, json.dumps(json_payload))
                        )
                        db.commit()
                except Exception as e:
                    app.logger.error(f"Failed to write to audit log: {e}")

            g.audit_log_function = log_action

            # Execute the original route function
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Authentication & Role-Based Access Control ---
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))

            db = get_db()
            user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

            if role and user['role'] not in role:
                return "<h1>Access Denied</h1><p>You do not have permission to view this page.</p>", 403

            g.user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Favicon Route ---
@app.route('/favicon.ico')
def favicon():
    return '', 204

# --- Global Error Handler ---
@app.errorhandler(Exception)
def handle_unhandled_error(e):
    app.logger.error(f"Unhandled error: {e}")
    return jsonify({"error": "An internal server error occurred. Please try again later."}), 500


# --- Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['name']

            # Audit Login
            db.execute(
                'INSERT INTO audit_logs (user_identity, action_type, source_ip, description) VALUES (?, ?, ?, ?)',
                (f"{user['name']} ({user['role']})", 'LOGIN', request.remote_addr, f"User '{user['name']}' logged in successfully.")
            )
            db.commit()

            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials. Please try again.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        db = get_db()
        user = db.execute('SELECT name, role FROM users WHERE id = ?', (user_id,)).fetchone()
        user_identity = f"{user['name']} ({user['role']})" if user else "Unknown User"

        db.execute(
            'INSERT INTO audit_logs (user_identity, action_type, source_ip, description) VALUES (?, ?, ?, ?)',
            (user_identity, 'LOGOUT', request.remote_addr, f"User '{user_identity}' logged out.")
        )
        db.commit()

    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required()
def dashboard():
    return render_template('index.html')

# --- API Endpoints for Dashboard ---
@app.route('/api/dashboard-stats')
@login_required(role=['DPO', 'Admin'])
def dashboard_stats():
    db = get_db()

    # Consent stats
    consent_stats = db.execute('SELECT status, COUNT(id) as count FROM consents GROUP BY status').fetchall()

    # Recent DSR Requests
    recent_dsr_requests = db.execute('''
        SELECT d.id, u.name as user_name, d.request_type, d.status, d.submitted_at
        FROM dsr_requests d
        JOIN users u ON d.user_id = u.id
        ORDER BY d.submitted_at DESC
        LIMIT 3
    ''').fetchall()

    # Processing registry count
    registry_count = db.execute('SELECT COUNT(id) as count FROM processing_registry').fetchone()['count']

    stats = {
        "consents": {row['status']: row['count'] for row in consent_stats},
        "open_incidents": 0, # No incidents
        "total_processing_activities": registry_count,
        "recent_dsr_requests": [_serialize_row(row) for row in recent_dsr_requests]
    }
    # DPO and Admins see all consents from all users
    # Also fetch inventory and checklist for the dashboard
    inventory = db.execute('SELECT * FROM personal_data_inventory').fetchall()
    checklist = db.execute('SELECT * FROM compliance_checklist').fetchall()
    stats['inventory'] = [dict(row) for row in inventory]
    stats['checklist'] = [dict(row) for row in checklist]
    return jsonify(stats)

@app.route('/api/compliance-checklist')
@login_required(role=['DPO', 'Admin'])
def get_compliance_checklist():
    db = get_db()
    checklist = db.execute('SELECT * FROM compliance_checklist').fetchall()
    return jsonify([dict(row) for row in checklist])

@app.route('/api/personal-data-inventory')
@login_required(role=['DPO', 'Admin'])
def get_personal_data_inventory():
    db = get_db()
    inventory = db.execute('SELECT * FROM personal_data_inventory').fetchall()
    return jsonify([dict(row) for row in inventory])

# --- User Profile Management ---
@app.route('/api/profile', methods=['GET'])
@login_required()
def get_profile():
    # g.user is already loaded by @login_required
    return jsonify(dict(g.user))

@app.route('/api/profile/update', methods=['POST'])
@login_required()
@audit_log('UPDATE', "User updated their profile information.")
def update_profile():
    data = request.form
    db = get_db()
    user_id = session['user_id']

    # Handle password change
    if data.get('new_password') and data.get('confirm_password'):
        if data['new_password'] == data['confirm_password']:
            password_hash = generate_password_hash(data['new_password'])
            db.execute('UPDATE users SET name = ?, password_hash = ? WHERE id = ?', (data['name'], password_hash, user_id))
        else:
            return jsonify({"error": "Passwords do not match"}), 400
    else:
        # Update name only
        db.execute('UPDATE users SET name = ? WHERE id = ?', (data['name'], user_id))

    db.commit()
    # Update session if name changed
    session['user_name'] = data['name']
    return jsonify({"success": True, "message": "Profile updated successfully"})




# --- DPO Specific Routes ---
@app.route('/processing-registry')
@login_required(role=['DPO', 'Admin'])
def processing_registry():
    db = get_db()
    query = request.args.get('q', '')

    if query:
        search_term = f"%{query}%"
        items = db.execute('SELECT * FROM processing_registry WHERE system_name LIKE ? OR purpose LIKE ? OR owner LIKE ?',
                           (search_term, search_term, search_term)).fetchall()
    else:
        items = db.execute('SELECT * FROM processing_registry').fetchall()

    return jsonify([dict(row) for row in items])


@app.route('/processing-registry/add', methods=['POST'])
@login_required(role=['DPO', 'Admin'])
@audit_log('CREATE', "Added new processing activity: '{system_name}'")
def add_processing_activity():
    data = request.form
    db = get_db()
    db.execute(
        'INSERT INTO processing_registry (system_name, purpose, data_categories, legal_basis, retention_period, owner) VALUES (?, ?, ?, ?, ?, ?)',
        (data['system_name'], data['purpose'], data['data_categories'], data['legal_basis'], data['retention_period'], data['owner'])
    )
    db.commit()
    return jsonify({"success": True, "message": "Processing activity added successfully."})

@app.route('/processing-registry/update/<int:item_id>', methods=['POST'])
@login_required(role=['DPO', 'Admin'])
@audit_log('UPDATE', "Updated processing activity ID {item_id}")
def update_processing_activity(item_id):
    data = request.form
    db = get_db()
    db.execute(
        'UPDATE processing_registry SET system_name = ?, purpose = ?, data_categories = ?, legal_basis = ?, retention_period = ?, owner = ? WHERE id = ?',
        (data['system_name'], data['purpose'], data['data_categories'], data['legal_basis'], data['retention_period'], data['owner'], item_id)
    )
    db.commit()
    return jsonify({"success": True, "message": "Processing activity updated successfully."})

@app.route('/processing-registry/delete/<int:item_id>', methods=['POST'])
@login_required(role=['DPO', 'Admin'])
@audit_log('DELETE', "Deleted processing activity ID {item_id}")
def delete_processing_activity(item_id):
    db = get_db()
    db.execute('DELETE FROM processing_registry WHERE id = ?', (item_id,))
    db.commit()
    return jsonify({"success": True})

# --- User Specific Routes ---
@app.route('/my-consents')
@login_required()
def my_consents():
    db = get_db()
    user_id = session['user_id']
    user_role = session['user_role']
    page = request.args.get('page', 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page

    if user_role in ['DPO', 'Admin']:
        # DPOs and Admins see all consents from all users
        total_count_query = 'SELECT COUNT(id) FROM consents'
        total_count_params = []
        items_query = '''
            SELECT c.id, c.touchpoint_name, c.status, c.timestamp, u.name as user_name
            FROM consents c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.timestamp DESC
            LIMIT ? OFFSET ?
        '''
        items_params = [per_page, offset]
    else:
        # Regular users only see their own consents
        total_count_query = 'SELECT COUNT(id) FROM consents WHERE user_id = ?'
        total_count_params = [user_id]
        items_query = 'SELECT id, touchpoint_name, status, timestamp FROM consents WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        items_params = [user_id, per_page, offset]

    total_count = db.execute(total_count_query, total_count_params).fetchone()[0]
    items = db.execute(items_query, items_params).fetchall()

    total_pages = (total_count + per_page - 1) // per_page

    return jsonify({
        "consents": [_serialize_row(row) for row in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_items": total_count
        }
    })

@app.route('/consents/update/<int:consent_id>', methods=['POST'])
@login_required()
@audit_log('UPDATE', "Updated consent ID {consent_id} to status '{status}'")
def update_consent_status(consent_id):
    new_status = request.form['status']
    db = get_db()
    user_id = session['user_id']
    user_role = session['user_role']

    # Authorization Check
    if user_role == 'User':
        # Regular users can only change their own consents.
        consent = db.execute('SELECT * FROM consents WHERE id = ? AND user_id = ?', (consent_id, user_id)).fetchone()
        if not consent:
            return jsonify({"error": "Permission Denied. You can only change your own consents."}), 403
    else:
        # Admins and DPOs can change any consent, but we check if it exists.
        consent = db.execute('SELECT * FROM consents WHERE id = ?', (consent_id,)).fetchone()
        if not consent:
            return jsonify({"error": "Consent record not found."}), 404

    if new_status in ['Active', 'Revoked']:
        db.execute('UPDATE consents SET status = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?', (new_status, consent_id))
        db.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Invalid Status"}), 400


# --- Admin Specific Routes ---
@app.route('/audit-logs')
@login_required(role=['Admin', 'DPO'])
def audit_logs():
    db = get_db()
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 15

    # Base query and params
    base_query = 'FROM audit_logs'
    count_query = 'SELECT COUNT(id) '
    select_query = 'SELECT * '
    order_query = ' ORDER BY timestamp DESC'
    limit_query = ' LIMIT ? OFFSET ?'
    params = []

    if query:
        search_term = f"%{query}%"
        where_clause = ' WHERE user_identity LIKE ? OR action_type LIKE ? OR description LIKE ?'
        base_query += where_clause
        params.extend([search_term, search_term, search_term])

    # Get total count for pagination
    total_count = db.execute(count_query + base_query, params).fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page

    # Get logs for the current page
    params.extend([per_page, (page - 1) * per_page])
    logs = db.execute(select_query + base_query + order_query + limit_query, params).fetchall()

    return jsonify({
        "logs": [_serialize_row(row) for row in logs],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_items": total_count
        }
    })


# --- Incident Management Routes (REMOVED) ---

@app.route('/users/list')
@login_required(role=['DPO', 'Admin'])
def list_dpo_admin_users():
    db = get_db()
    users = db.execute("SELECT id, name, role FROM users WHERE role IN ('DPO', 'Admin')").fetchall()
    return jsonify([dict(row) for row in users])


# --- Admin User Management ---
VALID_ROLES = ['User', 'DPO', 'Admin']
MIN_PASSWORD_LENGTH = 4

@app.route('/admin/users/list')
@login_required(role=['Admin'])
def admin_users_list():
    db = get_db()
    users = db.execute('SELECT id, name, email, role FROM users ORDER BY id').fetchall()
    return jsonify([dict(row) for row in users])

@app.route('/admin/users/add', methods=['POST'])
@login_required(role=['Admin'])
@audit_log('CREATE', "Created new user '{name}'.")
def admin_users_add():
    data = request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role')

    # Validation
    if not name or not email or not password or not role:
        return jsonify({"error": "Name, email, password, and role are all required."}), 400
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email format."}), 400
    if not is_strong_password(password):
        return jsonify({"error": "Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one number."}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": "Invalid role. Must be User, DPO, or Admin."}), 400

    db = get_db()
    existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    if existing:
        return jsonify({"error": "A user with that email already exists."}), 400

    password_hash = generate_password_hash(password)
    db.execute(
        'INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)',
        (name, email, password_hash, role)
    )
    db.commit()
    return jsonify({"success": True, "message": "User created successfully."})

@app.route('/admin/users/update/<int:user_id>', methods=['POST'])
@login_required(role=['Admin'])
@audit_log('UPDATE', "Updated user ID {user_id}.")
def admin_users_update(user_id):
    data = request.form
    name = (data.get('name') or '').strip()
    role = data.get('role')
    new_password = data.get('password')

    if not name or not role:
        return jsonify({"error": "Name and role are required."}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": "Invalid role. Must be User, DPO, or Admin."}), 400
    if new_password and not is_strong_password(new_password):
        return jsonify({"error": "Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one number."}), 400
    if new_password and len(new_password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters."}), 400

    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found."}), 404

    if new_password:
        db.execute(
            'UPDATE users SET name = ?, role = ?, password_hash = ? WHERE id = ?',
            (name, role, generate_password_hash(new_password), user_id)
        )
    else:
        # Email and password are preserved; only name/role change.
        db.execute(
            'UPDATE users SET name = ?, role = ? WHERE id = ?',
            (name, role, user_id)
        )
    db.commit()
    return jsonify({"success": True, "message": "User updated successfully."})

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required(role=['Admin'])
@audit_log('DELETE', "Deleted user ID {user_id}.")
def admin_users_delete(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found."}), 404

    # Guard 1: Cannot delete your own account
    if user_id == session['user_id']:
        return jsonify({"error": "You cannot delete your own account."}), 400

    # Guard 2: Cannot delete the last Admin
    if user['role'] == 'Admin':
        admin_count = db.execute("SELECT COUNT(id) FROM users WHERE role = 'Admin'").fetchone()[0]
        if admin_count <= 1:
            return jsonify({"error": "You cannot delete the last Admin user."}), 400

    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    return jsonify({"success": True, "message": "User deleted successfully."})


# --- Privacy Notice Management ---
@app.route('/privacy-notices')
@login_required(role=['DPO', 'Admin'])
def get_privacy_notices():
    db = get_db()
    notices = db.execute('SELECT * FROM privacy_notices ORDER BY updated_at DESC').fetchall()
    return jsonify([dict(row) for row in notices])

@app.route('/privacy-notices/add', methods=['POST'])
@login_required(role=['DPO', 'Admin'])
@audit_log('CREATE', "Created new privacy notice: '{title}'")
def add_privacy_notice():
    data = request.form
    db = get_db()
    db.execute(
        'INSERT INTO privacy_notices (title, version, content, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
        (data['title'], data['version'], data['content'])
    )
    db.commit()
    return jsonify({"success": True})

@app.route('/privacy-notices/update/<int:notice_id>', methods=['POST'])
@login_required(role=['DPO', 'Admin'])
@audit_log('UPDATE', "Updated privacy notice ID {notice_id}")
def update_privacy_notice(notice_id):
    data = request.form
    db = get_db()
    db.execute(
        'UPDATE privacy_notices SET title = ?, version = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (data['title'], data['version'], data['content'], notice_id)
    )
    db.commit()
    return jsonify({"success": True})

@app.route('/privacy-notices/publish/<int:notice_id>', methods=['POST'])
@login_required(role=['DPO', 'Admin'])
@audit_log('UPDATE', "Toggled publication status for notice ID {notice_id}")
def publish_privacy_notice(notice_id):
    db = get_db()
    notice = db.execute('SELECT is_published FROM privacy_notices WHERE id = ?', (notice_id,)).fetchone()
    if notice:
        new_status = not notice['is_published']
        if new_status:
            # If publishing, set the published_at to the current time
            db.execute(
                'UPDATE privacy_notices SET is_published = ?, published_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_status, notice_id)
            )
        else:
            # If un-publishing, set published_at to NULL
            db.execute(
                'UPDATE privacy_notices SET is_published = ?, published_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_status, notice_id)
            )
        db.commit()
    return jsonify({"success": True})


# --- DSR Request Management ---
@app.route('/dsr-requests')
@login_required(role=['DPO', 'Admin'])
def get_dsr_requests():
    db = get_db()
    requests = db.execute('''
        SELECT d.id, u.name as user_name, d.request_type, d.status, d.submitted_at
        FROM dsr_requests d
        JOIN users u ON d.user_id = u.id
        ORDER BY d.submitted_at DESC
    ''').fetchall()
    return jsonify([_serialize_row(row) for row in requests])

@app.route('/dsr-requests/update/<int:request_id>', methods=['POST'])
@login_required(role=['DPO', 'Admin'])
@audit_log('UPDATE', "Updated DSR Request ID {request_id}")
def update_dsr_request(request_id):
    data = request.form
    db = get_db()
    db.execute(
        'UPDATE dsr_requests SET status = ?, resolved_at = CURRENT_TIMESTAMP, resolution_notes = ? WHERE id = ?',
        (data['status'], data.get('resolution_notes', ''), request_id)
    )
    db.commit()
    return jsonify({"success": True})


# --- User-Facing API Endpoints ---

@app.route('/api/user-dashboard')
@login_required()
def user_dashboard():
    db = get_db()
    user_id = session['user_id']

    # Consent summary
    consents = db.execute('SELECT status, COUNT(id) as count FROM consents WHERE user_id = ? GROUP BY status', (user_id,)).fetchall()

    # Open DSR request count
    open_dsr_count = db.execute('SELECT COUNT(id) FROM dsr_requests WHERE user_id = ? AND status = "Pending"', (user_id,)).fetchone()[0]

    dashboard_data = {
        "consents": {row['status']: row['count'] for row in consents},
        "open_dsr_count": open_dsr_count,
    }
    return jsonify(dashboard_data)

@app.route('/api/my-data')
@login_required()
def my_data():
    db = get_db()
    user_id = session['user_id']
    inventory = db.execute('SELECT * FROM personal_data_inventory WHERE user_id = ?', (user_id,)).fetchall()
    return jsonify([dict(row) for row in inventory])

@app.route('/api/dsr/my')
@login_required()
def my_dsr_requests():
    db = get_db()
    user_id = session['user_id']
    requests = db.execute('''
        SELECT id, request_type, status, submitted_at, resolution_notes,
               CASE WHEN proof_document IS NOT NULL AND proof_document != '' THEN 1 ELSE 0 END as has_proof
        FROM dsr_requests
        WHERE user_id = ?
        ORDER BY submitted_at DESC
    ''', (user_id,)).fetchall()
    return jsonify([_serialize_row(row) for row in requests])

def _is_allowed_proof_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_PROOF_EXTENSIONS

@app.route('/api/dsr/submit', methods=['POST'])
@login_required()
@audit_log('CREATE', "User submitted a DSR request of type '{request_type}'.")
def submit_dsr():
    db = get_db()
    user_id = session['user_id']
    request_type = request.form.get('request_type')
    notes = request.form.get('notes', '') # Optional notes field

    if not request_type or request_type not in DSR_TYPES:
        return jsonify({"error": "Invalid or missing DSR request type."}), 400

    proof_filename = None
    if 'proof' in request.files:
        file = request.files['proof']
        if file and file.filename != '' and _is_allowed_proof_file(file.filename):
            # Check file size
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > MAX_PROOF_SIZE:
                 return jsonify({"error": f"File too large. Maximum size is {MAX_PROOF_SIZE/1024/1024}MB."}), 400
            file.seek(0) # Reset file pointer

            proof_filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, proof_filename))

    db.execute(
        'INSERT INTO dsr_requests (user_id, request_type, status, proof_document, resolution_notes) VALUES (?, ?, ?, ?, ?)',
        (user_id, request_type, 'Pending', proof_filename, notes)
    )
    db.commit()

    return jsonify({"success": True, "message": "DSR request submitted successfully."})

@app.route('/api/public-privacy-notices')
@login_required()
def public_privacy_notices():
    db = get_db()
    notices = db.execute('SELECT title, version, content, published_at FROM privacy_notices WHERE is_published = 1 ORDER BY published_at DESC').fetchall()
    return jsonify([dict(row) for row in notices])


# --- Export Endpoints ---
@app.route('/export/pdf')
@login_required(role=['Admin', 'DPO'])
@audit_log('EXPORT', "Exported audit logs to PDF.")
def export_pdf():
    try:
        # This is a simplified simulation for PDF generation
        db = get_db()
        logs = db.execute('SELECT * FROM audit_logs ORDER BY timestamp DESC').fetchall()

        # Basic assertion to simulate a potential failure point
        assert len(logs) > 0, "No logs to export, demonstrating graceful failure."

        html = "<h1>Audit Log Report</h1>"
        html += "<table border='1'><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Description</th></tr>"
        for log in logs:
            html += f"<tr><td>{log['timestamp']}</td><td>{log['user_identity']}</td><td>{log['action_type']}</td><td>{log['description']}</td></tr>"
        html += "</table>"

        # In a real app, you'd use a library like WeasyPrint or FPDF to generate a real PDF
        return html
    except AssertionError as e:
        # Log the specific assertion error for debugging
        app.logger.warning(f"PDF Export failed: {e}")
        # Return a user-friendly HTML error page
        return jsonify({"error": "An internal server error occurred."}), 500
    except Exception as e:
        # General exception handler
        app.logger.error(f"An unexpected error occurred during PDF export: {e}")
        return "<h1>Internal Server Error</h1><p>An unexpected error occurred. Please contact support.</p>", 500

@app.route('/export/excel')
@login_required(role=['Admin', 'DPO'])
@audit_log('EXPORT', "Exported processing registry to Excel/CSV.")
def export_excel():
    try:
        db = get_db()
        registry_items = db.execute('SELECT * FROM processing_registry').fetchall()

        # Basic assertion to simulate a potential failure point
        assert len(registry_items) > 0, "No processing activities to export."

        si = StringIO()
        cw = csv.writer(si)

        # Write header
        if registry_items:
            cw.writerow(registry_items[0].keys())
            cw.writerows([dict(row).values() for row in registry_items])

        output = si.getvalue()
        si.close()

        return output, 200, {
            'Content-Disposition': 'attachment; filename="processing_registry.csv"',
            'Content-Type': 'text/csv'
        }
    except AssertionError as e:
        app.logger.warning(f"CSV Export failed: {e}")
        # Return a JSON error for API-like behavior
        return jsonify({"error": "An internal server error occurred."}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during CSV export: {e}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

@app.route('/test-submit')
def test_submit_page():
    return send_from_directory('.', 'submit_form.html')

if __name__ == '__main__':
    app.run(debug=True)