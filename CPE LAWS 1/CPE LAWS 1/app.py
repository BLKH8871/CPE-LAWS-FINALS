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
import re

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_fallback_key_in_case_env_is_missing')
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compliance_system.db')

# --- DSR Proof Upload Configuration ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'uploads')
ALLOWED_PROOF_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp'}
MAX_PROOF_SIZE = 5 * 1024 * 1024  # 5 MB
DSR_TYPES = ['Access', 'Rectification', 'Erasure', 'Restriction', 'Portability', 'Objection']
SECURITY_ACTIONS = ('LOGIN', 'LOGOUT', 'CREATE', 'UPDATE', 'DELETE')

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
@app.after_request
def perform_audit_log(response):
    if hasattr(g, 'audit_log_function'):
        g.audit_log_function(response)
    return response

def audit_log(action_type, description_template):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            def log_action(response):
                if not (200 <= response.status_code < 400):
                    return
                try:
                    db = get_db()
                    if 'user_id' in session:
                        user = db.execute('SELECT name, role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
                        user_identity = f"{user['name']} ({user['role']})" if user else "Unknown User"
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
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Authentication & Role-Based Access Control ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.endpoint and (request.endpoint.startswith('api.') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
                return jsonify(error="Authentication required"), 401
            return redirect(url_for('login'))

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        if user is None:
            session.clear() # Clear invalid session
            if request.endpoint and (request.endpoint.startswith('api.') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
                return jsonify(error="Invalid session. Please log in again."), 401
            return redirect(url_for('login'))

        g.user = user
        return f(*args, **kwargs)
    return decorated_function

def check_access(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or g.user['role'] != required_role:
                if request.endpoint and (request.endpoint.startswith('api.') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
                    return jsonify(error=f"Forbidden: You need the '{required_role}' role for this action."), 403
                return "<h1>Access Denied</h1><p>You do not have the required permissions.</p>", 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user') or g.user['role'] not in roles:
                if request.endpoint and (request.endpoint.startswith('api.') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'):
                    return jsonify(error=f"Forbidden: You need one of the following roles: {', '.join(roles)}"), 403
                return "<h1>Access Denied</h1><p>You do not have the required permissions.</p>", 403
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
    # Log the error regardless of environment
    app.logger.error(f"Unhandled exception: {e}", exc_info=True)

    # For API requests in development, return a detailed JSON error
    is_api_request = request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    is_development = os.environ.get('FLASK_ENV') == 'development' or app.debug

    if is_api_request:
        if is_development:
            import traceback
            return jsonify({
                "error": "Internal Server Error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }), 500
        else:
            return jsonify({"error": "An internal server error occurred. Please try again later."}), 500

    # For non-API requests in development, let the interactive debugger handle it
    if is_development:
        raise e

    # For non-API requests in production, show a generic HTML error page
    return "<h1>Internal Server Error</h1><p>Sorry, something went wrong.</p>", 500


# --- Helper Functions ---
def is_valid_email(email):
    """Basic email validation."""
    if not email:
        return False
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_strong_password(password):
    """Password must be >= 8 chars, with at least one uppercase, one lowercase, and one number."""
    if len(password) < 8:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True


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
@login_required
def dashboard():
    return render_template('index.html')

# --- API Endpoints for Dashboard ---
@app.route('/api/dashboard-stats')
@login_required
@check_access('DPO')
def dashboard_stats():
    db = get_db()
    consent_stats = db.execute('SELECT status, COUNT(id) as count FROM consents GROUP BY status').fetchall()
    recent_dsr_requests = db.execute('''
        SELECT d.id, u.name as user_name, d.request_type, d.status, d.submitted_at
        FROM dsr_requests d JOIN users u ON d.user_id = u.id
        ORDER BY d.submitted_at DESC LIMIT 3
    ''').fetchall()
    registry_count = db.execute('SELECT COUNT(id) as count FROM processing_registry').fetchone()['count']
    stats = {
        "consents": {row['status']: row['count'] for row in consent_stats},
        "open_incidents": 0,
        "total_processing_activities": registry_count,
        "recent_dsr_requests": [_serialize_row(row) for row in recent_dsr_requests]
    }
    inventory = db.execute('SELECT * FROM personal_data_inventory').fetchall()
    checklist = db.execute('SELECT * FROM compliance_checklist').fetchall()
    stats['inventory'] = [dict(row) for row in inventory]
    stats['checklist'] = [dict(row) for row in checklist]
    return jsonify(stats)

@app.route('/api/compliance-checklist')
@login_required
@check_access('DPO')
def get_compliance_checklist():
    db = get_db()
    checklist = db.execute('SELECT * FROM compliance_checklist').fetchall()
    return jsonify([dict(row) for row in checklist])

@app.route('/api/personal-data-inventory')
@login_required
@check_access('DPO')
def get_personal_data_inventory():
    db = get_db()
    inventory = db.execute('SELECT * FROM personal_data_inventory').fetchall()
    return jsonify([dict(row) for row in inventory])

# --- User Profile Management ---
@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    return jsonify(dict(g.user))

@app.route('/api/profile/update', methods=['POST'])
@login_required
@audit_log('UPDATE', "User updated their profile information.")
def update_profile():
    data = request.form
    name = (data.get('name') or '').strip()

    if not name:
        return jsonify({"error": "Name cannot be empty."}), 400

    db = get_db()
    user_id = session['user_id']
    if data.get('new_password') and data.get('confirm_password'):
        if data['new_password'] == data['confirm_password']:
            if not is_strong_password(data['new_password']):
                 return jsonify({"error": "Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one number."}), 400
            password_hash = generate_password_hash(data['new_password'])
            db.execute('UPDATE users SET name = ?, password_hash = ? WHERE id = ?', (name, password_hash, user_id))
        else:
            return jsonify({"error": "Passwords do not match"}), 400
    else:
        db.execute('UPDATE users SET name = ? WHERE id = ?', (name, user_id))
    db.commit()
    session['user_name'] = name
    return jsonify({"success": True, "message": "Profile updated successfully"})

# --- DPO Specific Routes ---
@app.route('/processing-registry')
@login_required
@check_access('DPO')
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
@login_required
@check_access('DPO')
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
@login_required
@check_access('DPO')
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
@login_required
@check_access('DPO')
@audit_log('DELETE', "Deleted processing activity ID {item_id}")
def delete_processing_activity(item_id):
    db = get_db()
    db.execute('DELETE FROM processing_registry WHERE id = ?', (item_id,))
    db.commit()
    return jsonify({"success": True})

# --- User Specific Routes ---
@app.route('/my-consents')
@login_required
def my_consents():
    db = get_db()
    user_id = session['user_id']
    user_role = session['user_role']
    page = request.args.get('page', 1, type=int)
    per_page = 15
    offset = (page - 1) * per_page
    if user_role in ['DPO', 'Admin']:
        total_count_query = 'SELECT COUNT(id) FROM consents'
        total_count_params = []
        items_query = '''
            SELECT c.id, c.touchpoint_name, c.status, c.timestamp, u.name as user_name
            FROM consents c JOIN users u ON c.user_id = u.id
            ORDER BY c.timestamp DESC LIMIT ? OFFSET ?
        '''
        items_params = [per_page, offset]
    else:
        total_count_query = 'SELECT COUNT(id) FROM consents WHERE user_id = ?'
        total_count_params = [user_id]
        items_query = 'SELECT id, touchpoint_name, status, timestamp FROM consents WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        items_params = [user_id, per_page, offset]
    total_count = db.execute(total_count_query, total_count_params).fetchone()[0]
    items = db.execute(items_query, items_params).fetchall()
    total_pages = (total_count + per_page - 1) // per_page
    return jsonify({
        "consents": [_serialize_row(row) for row in items],
        "pagination": { "page": page, "per_page": per_page, "total_pages": total_pages, "total_items": total_count }
    })

@app.route('/consents/update/<int:consent_id>', methods=['POST'])
@login_required
@audit_log('UPDATE', "Updated consent ID {consent_id} to status '{status}'")
def update_consent_status(consent_id):
    new_status = request.form['status']
    db = get_db()
    user_id = g.user['id']
    user_role = g.user['role']

    consent = db.execute('SELECT * FROM consents WHERE id = ?', (consent_id,)).fetchone()

    if not consent:
        return jsonify({"error": "Consent record not found."}), 404

    # Authorization Check: Must be the owner or a DPO.
    if user_role != 'DPO' and consent['user_id'] != user_id:
        return jsonify({"error": "Permission Denied. You do not have access to modify this consent record."}), 403

    if new_status in ['Active', 'Revoked']:
        db.execute('UPDATE consents SET status = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?', (new_status, consent_id))
        db.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Invalid Status"}), 400

# --- Admin Specific Routes ---
@app.route('/api/admin-dashboard')
@login_required
@check_access('Admin')
def admin_dashboard_stats():
    db = get_db()
    total_users = db.execute("SELECT COUNT(id) FROM users").fetchone()[0]
    admin_users = db.execute("SELECT COUNT(id) FROM users WHERE role = 'Admin'").fetchone()[0]
    twenty_four_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=24)
    audit_events_24h = db.execute(
        "SELECT COUNT(id) FROM audit_logs WHERE timestamp >= ?", (twenty_four_hours_ago,)
    ).fetchone()[0]
    role_distribution = db.execute("SELECT role, COUNT(id) as count FROM users GROUP BY role").fetchall()
    placeholders = ', '.join('?' for _ in SECURITY_ACTIONS)
    recent_security_logs = db.execute(
        f"SELECT user_identity, action_type, description, timestamp FROM audit_logs WHERE action_type IN ({placeholders}) ORDER BY timestamp DESC LIMIT 5",
        SECURITY_ACTIONS
    ).fetchall()
    stats = {
        "total_users": total_users,
        "admin_users": admin_users,
        "audit_events_24h": audit_events_24h,
        "role_distribution": {row['role']: row['count'] for row in role_distribution},
        "recent_security_logs": [_serialize_row(row) for row in recent_security_logs]
    }
    return jsonify(stats)

@app.route('/audit-logs')
@login_required
@require_role('DPO', 'Admin')
def audit_logs():
    db = get_db()
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 15
    params = []

    base_query = 'FROM audit_logs'
    where_clauses = []

    if g.user['role'] == 'Admin':
        # Admin sees only specific security-related actions
        # This is now safe from SQL injection as the list is static, but parameterizing is best practice.
        placeholders = ', '.join(['?'] * len(SECURITY_ACTIONS))
        where_clauses.append(f"action_type IN ({placeholders})")
        params.extend(SECURITY_ACTIONS)
    # DPO has no role-based filter and sees all logs by default

    if query:
        search_term = f"%{query}%"
        where_clauses.append('(user_identity LIKE ? OR action_type LIKE ? OR description LIKE ?)')
        params.extend([search_term, search_term, search_term])

    if where_clauses:
        base_query += ' WHERE ' + ' AND '.join(where_clauses)

    count_query = 'SELECT COUNT(id) ' + base_query
    total_count = db.execute(count_query, params).fetchone()[0]

    total_pages = (total_count + per_page - 1) // per_page

    select_query = 'SELECT * ' + base_query + ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    logs = db.execute(select_query, params).fetchall()

    return jsonify({
        "logs": [_serialize_row(row) for row in logs],
        "pagination": { "page": page, "per_page": per_page, "total_pages": total_pages, "total_items": total_count }
    })

@app.route('/users/list')
@login_required
@check_access('DPO')
def list_dpo_admin_users():
    db = get_db()
    users = db.execute("SELECT id, name, role FROM users WHERE role IN ('DPO', 'Admin')").fetchall()
    return jsonify([dict(row) for row in users])

# --- Admin User Management ---
VALID_ROLES = ['User', 'DPO', 'Admin']
MIN_PASSWORD_LENGTH = 8

@app.route('/admin/users/list')
@login_required
@check_access('Admin')
def admin_users_list():
    db = get_db()
    users = db.execute('SELECT id, name, email, role FROM users ORDER BY id').fetchall()
    return jsonify([dict(row) for row in users])

@app.route('/admin/users/add', methods=['POST'])
@login_required
@check_access('Admin')
@audit_log('CREATE', "Created new user '{name}'.")
def admin_users_add():
    data = request.form
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role')
    if not all([name, email, password, role]):
        return jsonify({"error": "Name, email, password, and role are all required."}), 400
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email format."}), 400
    if not is_strong_password(password):
        return jsonify({"error": "Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one number."}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": "Invalid role. Must be User, DPO, or Admin."}), 400
    db = get_db()
    if db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
        return jsonify({"error": "A user with that email already exists."}), 400
    password_hash = generate_password_hash(password)
    db.execute('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)', (name, email, password_hash, role))
    db.commit()
    return jsonify({"success": True, "message": "User created successfully."})

@app.route('/admin/users/update/<int:user_id>', methods=['POST'])
@login_required
@check_access('Admin')
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
    db = get_db()
    if not db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone():
        return jsonify({"error": "User not found."}), 404
    if new_password:
        db.execute('UPDATE users SET name = ?, role = ?, password_hash = ? WHERE id = ?', (name, role, generate_password_hash(new_password), user_id))
    else:
        db.execute('UPDATE users SET name = ?, role = ? WHERE id = ?', (name, role, user_id))
    db.commit()
    return jsonify({"success": True, "message": "User updated successfully."})

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@check_access('Admin')
@audit_log('DELETE', "Deleted user ID {user_id}.")
def admin_users_delete(user_id):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found."}), 404
    if user_id == session['user_id']:
        return jsonify({"error": "You cannot delete your own account."}), 400
    if user['role'] == 'Admin':
        if db.execute("SELECT COUNT(id) FROM users WHERE role = 'Admin'").fetchone()[0] <= 1:
            return jsonify({"error": "You cannot delete the last Admin user."}), 400
    db.execute('DELETE FROM users WHERE id = ?', (user_id,))
    db.commit()
    return jsonify({"success": True, "message": "User deleted successfully."})

# --- Privacy Notice Management ---
@app.route('/privacy-notices')
@login_required
@check_access('DPO')
def get_privacy_notices():
    db = get_db()
    notices = db.execute('SELECT * FROM privacy_notices ORDER BY updated_at DESC').fetchall()
    return jsonify([dict(row) for row in notices])

@app.route('/privacy-notices/add', methods=['POST'])
@login_required
@check_access('DPO')
@audit_log('CREATE', "Created new privacy notice: '{title}'")
def add_privacy_notice():
    data = request.form
    db = get_db()
    db.execute('INSERT INTO privacy_notices (title, version, content, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)', (data['title'], data['version'], data['content']))
    db.commit()
    return jsonify({"success": True})

@app.route('/privacy-notices/update/<int:notice_id>', methods=['POST'])
@login_required
@check_access('DPO')
@audit_log('UPDATE', "Updated privacy notice ID {notice_id}")
def update_privacy_notice(notice_id):
    data = request.form
    db = get_db()
    db.execute('UPDATE privacy_notices SET title = ?, version = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (data['title'], data['version'], data['content'], notice_id))
    db.commit()
    return jsonify({"success": True})

@app.route('/privacy-notices/publish/<int:notice_id>', methods=['POST'])
@login_required
@check_access('DPO')
@audit_log('UPDATE', "Toggled publication status for notice ID {notice_id}")
def publish_privacy_notice(notice_id):
    db = get_db()
    notice = db.execute('SELECT is_published FROM privacy_notices WHERE id = ?', (notice_id,)).fetchone()
    if notice:
        new_status = not notice['is_published']
        if new_status:
            db.execute('UPDATE privacy_notices SET is_published = ?, published_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_status, notice_id))
        else:
            db.execute('UPDATE privacy_notices SET is_published = ?, published_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_status, notice_id))
        db.commit()
    return jsonify({"success": True})

# --- DSR Request Management ---
@app.route('/dsr-requests')
@login_required
@check_access('DPO')
def get_dsr_requests():
    db = get_db()
    requests = db.execute('''
        SELECT d.id, u.name as user_name, d.request_type, d.status, d.submitted_at
        FROM dsr_requests d JOIN users u ON d.user_id = u.id
        ORDER BY d.submitted_at DESC
    ''').fetchall()
    return jsonify([_serialize_row(row) for row in requests])

@app.route('/dsr-requests/update/<int:request_id>', methods=['POST'])
@login_required
@check_access('DPO')
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
@login_required
def user_dashboard():
    db = get_db()
    user_id = session['user_id']
    consents = db.execute('SELECT status, COUNT(id) as count FROM consents WHERE user_id = ? GROUP BY status', (user_id,)).fetchall()
    open_dsr_count = db.execute('SELECT COUNT(id) FROM dsr_requests WHERE user_id = ? AND status = "Pending"', (user_id,)).fetchone()[0]
    recent_dsr_requests = db.execute('''
        SELECT id, request_type, status, submitted_at FROM dsr_requests
        WHERE user_id = ? ORDER BY submitted_at DESC LIMIT 3
    ''', (user_id,)).fetchall()
    return jsonify({
        "consents": {row['status']: row['count'] for row in consents},
        "open_dsr_count": open_dsr_count,
        "recent_dsr_requests": [_serialize_row(row) for row in recent_dsr_requests]
    })

@app.route('/api/my-data')
@login_required
def my_data():
    db = get_db()
    user_id = session['user_id']
    inventory = db.execute('SELECT * FROM personal_data_inventory WHERE user_id = ?', (user_id,)).fetchall()
    return jsonify([dict(row) for row in inventory])

@app.route('/api/dsr/my')
@login_required
def my_dsr_requests():
    db = get_db()
    user_id = session['user_id']
    requests = db.execute('''
        SELECT id, request_type, status, submitted_at, description, resolution_notes,
               CASE WHEN proof_document IS NOT NULL AND proof_document != '' THEN 1 ELSE 0 END as has_proof
        FROM dsr_requests WHERE user_id = ? ORDER BY submitted_at DESC
    ''', (user_id,)).fetchall()
    return jsonify([_serialize_row(row) for row in requests])

def _is_allowed_proof_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PROOF_EXTENSIONS

@app.route('/api/dsr/submit', methods=['POST'])
@login_required
@audit_log('CREATE', "User submitted a DSR request of type '{request_type}'.")
def submit_dsr():
    db = get_db()
    user_id = session['user_id']
    request_type = request.form.get('request_type')
    notes = request.form.get('notes', '')
    if not request_type or request_type not in DSR_TYPES:
        return jsonify({"error": "Invalid or missing DSR request type."}), 400
    proof_filename = None
    if 'proof' in request.files:
        file = request.files['proof']
        if file and file.filename != '' and _is_allowed_proof_file(file.filename):
            file.seek(0, os.SEEK_END)
            file_length = file.tell()
            if file_length > MAX_PROOF_SIZE:
                 return jsonify({"error": f"File too large. Maximum size is {MAX_PROOF_SIZE/1024/1024}MB."}), 400
            file.seek(0)
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            original_filename = secure_filename(file.filename)
            proof_filename = f"{user_id}_{timestamp}_{original_filename}"
            file.save(os.path.join(UPLOAD_FOLDER, proof_filename))
    app.logger.info(f"Proof filename for DB insert: {proof_filename}")
    db.execute(
        'INSERT INTO dsr_requests (user_id, request_type, description, proof_document, status) VALUES (?, ?, ?, ?, ?)',
        (user_id, request_type, notes, proof_filename, 'Pending')
    )
    db.commit()
    return jsonify({"success": True, "message": "DSR request submitted successfully."})

@app.route('/api/public-privacy-notices')
@login_required
def public_privacy_notices():
    db = get_db()
    notices = db.execute('SELECT title, version, content, published_at FROM privacy_notices WHERE is_published = 1 ORDER BY published_at DESC').fetchall()
    return jsonify([dict(row) for row in notices])

# --- Export Endpoints ---
@app.route('/export/pdf')
@login_required
@check_access('DPO')
@audit_log('EXPORT', "Exported audit logs to PDF.")
def export_pdf():
    try:
        db = get_db()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = 'SELECT * FROM audit_logs'
        params = []
        where_clauses = []

        if start_date:
            where_clauses.append('timestamp >= ?')
            params.append(start_date)
        if end_date:
            # Add 1 day to end_date to include the entire day
            end_date_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=1)
            where_clauses.append('timestamp < ?')
            params.append(end_date_dt.strftime('%Y-%m-%d'))

        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)

        query += ' ORDER BY timestamp DESC'

        logs = db.execute(query, params).fetchall()

        assert len(logs) > 0, "No logs to export for the selected date range."

        report_title = "Audit Log Report"
        if start_date and end_date:
            report_title += f" ({start_date} to {end_date})"
        elif start_date:
            report_title += f" (from {start_date})"
        elif end_date:
            report_title += f" (until {end_date})"

        html = f"<h1>{report_title}</h1><table border='1'><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Description</th></tr>"
        for log in logs:
            html += f"<tr><td>{log['timestamp']}</td><td>{log['user_identity']}</td><td>{log['action_type']}</td><td>{log['description']}</td></tr>"
        html += "</table>"
        return html
    except AssertionError as e:
        app.logger.warning(f"PDF Export failed: {e}")
        return f"<h1>No Data</h1><p>{e}</p>", 404
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during PDF export: {e}")
        return "<h1>Internal Server Error</h1><p>An unexpected error occurred. Please contact support.</p>", 500

@app.route('/export/excel')
@login_required
@check_access('DPO')
@audit_log('EXPORT', "Exported processing registry to Excel/CSV.")
def export_excel():
    try:
        db = get_db()
        registry_items = db.execute('SELECT * FROM processing_registry').fetchall()
        assert len(registry_items) > 0, "No processing activities to export."
        si = StringIO()
        cw = csv.writer(si)
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
        return jsonify({"error": "An internal server error occurred."}), 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during CSV export: {e}")
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

@app.route('/test-submit')
def test_submit_page():
    return send_from_directory('.', 'submit_form.html')

if __name__ == '__main__':
    app.run(debug=True)
