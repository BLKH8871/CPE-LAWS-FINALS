"""
Data Privacy Compliance Management System (DPCMS)
=================================================
A localized LegalTech portal enforcing the Philippine Data Privacy Act of 2012
(RA 10173): Transparency, Legitimate Purpose, Proportionality.

Stack: Flask + SQLite3 + Jinja2/Tailwind(CDN)/Vanilla JS.

Run:
    pip install flask
    python app.py
Then open http://127.0.0.1:5000

Demo accounts (seeded on first run):
    admin@dpcms.ph / admin123   (System Administrator)
    dpo@dpcms.ph   / dpo123     (Data Protection Officer)
    user@dpcms.ph  / user123    (Regular Employee)
"""

import csv
import functools
import io
import json
import os
import sqlite3
from datetime import datetime

from flask import (Flask, Response, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "dpcms.db")
SCHEMA = os.path.join(BASE_DIR, "schema.sql")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("DPCMS_SECRET", os.urandom(24).hex())

# Human-readable role labels used across the UI
ROLE_LABELS = {
    "Admin": "System Administrator",
    "DPO": "Data Protection Officer",
    "User": "Regular Employee",
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables from schema.sql and seed demo data on first run."""
    first_run = not os.path.exists(DATABASE)
    db = sqlite3.connect(DATABASE)
    with open(SCHEMA, "r", encoding="utf-8") as f:
        db.executescript(f.read())

    seed_users = [
        ("System Administrator", "admin@dpcms.ph", "admin123", "Admin"),
        ("Maria Santos, CIPM", "dpo@dpcms.ph", "dpo123", "DPO"),
        ("Juan dela Cruz", "user@dpcms.ph", "user123", "User"),
    ]
    for name, email, pw, role in seed_users:
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
            (name, email, generate_password_hash(pw), role),
        )

    seed_registry = [
        ("HRIS Payroll", "Salary computation and statutory remittance (SSS, PhilHealth, Pag-IBIG, BIR)",
         "Name, TIN, SSS No., Bank Account, Salary Grade", "Legal Obligation", "10 years after separation", "HR Department"),
        ("Recruitment Portal", "Evaluation of job applicants for employment suitability",
         "Name, CV, Contact Details, Educational Records", "Consent", "1 year from application date", "Talent Acquisition"),
        ("CCTV Monitoring", "Physical security and safety of premises",
         "Facial Images, Timestamped Footage", "Legitimate Interest", "30 days rolling deletion", "Facilities & Security"),
        ("Customer CRM", "Order fulfillment, billing, and after-sales support",
         "Name, Address, Email, Purchase History", "Contract", "5 years from last transaction", "Sales Operations"),
        ("Health Declaration DB", "Occupational safety and health compliance (DOLE)",
         "Medical Certificates, Vaccination Status", "Legal Obligation", "3 years", "Clinic / HR"),
    ]
    db.executemany(
        """INSERT INTO processing_registry
           (system_name, purpose, data_categories, legal_basis, retention_period, owner)
           VALUES (?,?,?,?,?,?)""",
        seed_registry,
    )

    seed_consents = [
        (3, "Employee Onboarding Form", "Active"),
        (3, "Company Newsletter", "Active"),
        (3, "Photo/Video Publication Waiver", "Pending"),
        (3, "Third-Party Wellness Program", "Revoked"),
        (2, "Employee Onboarding Form", "Active"),
        (1, "Employee Onboarding Form", "Active"),
    ]
    db.executemany(
        "INSERT INTO consents (user_id, touchpoint_name, status) VALUES (?,?,?)",
        seed_consents,
    )

    db.execute(
        "INSERT INTO audit_logs (user_identity, action_type, source_ip, json_payload) VALUES (?,?,?,?)",
        ("system", "CREATE", "127.0.0.1",
         json.dumps({"event": "database_initialized", "tables": ["users", "consents", "processing_registry", "audit_logs"]})),
    )

    db.commit()
    db.close()
    if first_run:
        print(" * Database initialized with demo data ->", DATABASE)


# ---------------------------------------------------------------------------
# Audit Trail Middleware (RA 10173 accountability principle)
# ---------------------------------------------------------------------------
def write_audit(action_type, payload, user_identity=None):
    """Low-level writer: chronological, immutable record of a sensitive action."""
    db = get_db()
    db.execute(
        """INSERT INTO audit_logs (timestamp, user_identity, action_type, source_ip, json_payload)
           VALUES (?,?,?,?,?)""",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_identity or session.get("email", "anonymous"),
            request.headers.get("X-Forwarded-For", request.remote_addr or "unknown"),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    db.commit()


def audited(action_type):
    """
    Decorator that intercepts sensitive database actions. After the wrapped
    view succeeds, it records who did what, when, and from which IP. The view
    can enrich the record by setting g.audit_payload before returning.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            g.audit_payload = {}
            response = view(*args, **kwargs)
            payload = {
                "endpoint": request.endpoint,
                "method": request.method,
                "path": request.path,
                **g.audit_payload,
            }
            write_audit(action_type, payload)
            return response
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# Authentication & RBAC
# ---------------------------------------------------------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Server-side RBAC guard — the JS sidebar hiding is cosmetic; this is the
    actual security boundary."""
    def decorator(view):
        @functools.wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                write_audit("UPDATE", {
                    "event": "access_denied",
                    "attempted_path": request.path,
                    "held_role": session.get("role"),
                    "required_roles": list(roles),
                })
                return render_template("403.html",
                                       role_label=ROLE_LABELS.get(session.get("role"), "Unknown")), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_identity():
    return {
        "current_role": session.get("role"),
        "current_name": session.get("name"),
        "current_email": session.get("email"),
        "role_label": ROLE_LABELS.get(session.get("role", ""), ""),
    }


@app.route("/", methods=["GET"])
def root():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        row = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["user_id"] = row["id"]
            session["name"] = row["name"]
            session["email"] = row["email"]
            session["role"] = row["role"]
            write_audit("LOGIN", {"event": "login_success"}, user_identity=email)
            return redirect(url_for("dashboard"))
        error = "Invalid credentials. This attempt has been recorded."
        write_audit("LOGIN", {"event": "login_failed", "attempted_email": email},
                    user_identity=email or "anonymous")
    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    write_audit("LOGOUT", {"event": "logout"})
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard (single template, role-aware content)
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    stats = {
        "registry_count": db.execute("SELECT COUNT(*) c FROM processing_registry").fetchone()["c"],
        "consent_active": db.execute("SELECT COUNT(*) c FROM consents WHERE status='Active'").fetchone()["c"],
        "consent_pending": db.execute("SELECT COUNT(*) c FROM consents WHERE status='Pending'").fetchone()["c"],
        "consent_revoked": db.execute("SELECT COUNT(*) c FROM consents WHERE status='Revoked'").fetchone()["c"],
        "audit_count": db.execute("SELECT COUNT(*) c FROM audit_logs").fetchone()["c"],
        "user_count": db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"],
    }
    recent_audit = db.execute(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT 8"
    ).fetchall() if session["role"] == "Admin" else []
    my_consents = db.execute(
        "SELECT * FROM consents WHERE user_id = ? ORDER BY id DESC", (session["user_id"],)
    ).fetchall()
    return render_template("index.html", stats=stats,
                           recent_audit=recent_audit, my_consents=my_consents)


# ---------------------------------------------------------------------------
# Consent Management (all roles see their own; DPO/Admin see all)
# ---------------------------------------------------------------------------
@app.route("/consents")
@login_required
def consents():
    db = get_db()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    sql = """SELECT c.*, u.name AS owner_name, u.email AS owner_email
             FROM consents c JOIN users u ON u.id = c.user_id"""
    where, params = [], []

    if session["role"] == "User":
        where.append("c.user_id = ?")
        params.append(session["user_id"])
    if q:
        where.append("(c.touchpoint_name LIKE ? OR u.name LIKE ? OR u.email LIKE ?)")
        params += [f"%{q}%"] * 3
    if status in ("Active", "Pending", "Revoked"):
        where.append("c.status = ?")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.timestamp DESC"

    rows = db.execute(sql, params).fetchall()
    return render_template("consents.html", consents=rows, q=q, status=status)


@app.route("/consents/create", methods=["POST"])
@login_required
@audited("CREATE")
def consent_create():
    touchpoint = request.form.get("touchpoint_name", "").strip()
    if not touchpoint:
        flash("Touchpoint name is required.", "error")
        return redirect(url_for("consents"))
    db = get_db()
    cur = db.execute(
        "INSERT INTO consents (user_id, touchpoint_name, status) VALUES (?,?, 'Pending')",
        (session["user_id"], touchpoint),
    )
    db.commit()
    g.audit_payload = {"table": "consents", "record_id": cur.lastrowid,
                       "touchpoint": touchpoint, "initial_status": "Pending"}
    flash("Consent request submitted for review.", "success")
    return redirect(url_for("consents"))


@app.route("/consents/<int:cid>/status", methods=["POST"])
@login_required
@audited("UPDATE")
def consent_update(cid):
    new_status = request.form.get("status", "")
    if new_status not in ("Active", "Pending", "Revoked"):
        flash("Invalid status value.", "error")
        return redirect(url_for("consents"))

    db = get_db()
    row = db.execute("SELECT * FROM consents WHERE id = ?", (cid,)).fetchone()
    if row is None:
        flash("Consent record not found.", "error")
        return redirect(url_for("consents"))

    # A data subject may revoke their own consent (RA 10173 right to object);
    # only the DPO/Admin may approve (activate) or reinstate.
    is_owner = row["user_id"] == session["user_id"]
    is_officer = session["role"] in ("Admin", "DPO")
    if not (is_officer or (is_owner and new_status == "Revoked")):
        flash("You are not authorized to change this consent.", "error")
        return redirect(url_for("consents"))

    db.execute(
        "UPDATE consents SET status = ?, timestamp = ? WHERE id = ?",
        (new_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cid),
    )
    db.commit()
    g.audit_payload = {"table": "consents", "record_id": cid,
                       "old_status": row["status"], "new_status": new_status,
                       "data_subject_id": row["user_id"]}
    flash(f"Consent #{cid} set to {new_status}.", "success")
    return redirect(url_for("consents"))


# ---------------------------------------------------------------------------
# Data Processing Registry (DPO and Admin only)
# ---------------------------------------------------------------------------
LEGAL_BASES = ["Consent", "Contract", "Legal Obligation",
               "Vital Interest", "Public Task", "Legitimate Interest"]


@app.route("/registry")
@role_required("DPO", "Admin")
def registry():
    db = get_db()
    q = request.args.get("q", "").strip()
    basis = request.args.get("basis", "").strip()

    sql = "SELECT * FROM processing_registry"
    where, params = [], []
    if q:
        where.append("""(system_name LIKE ? OR purpose LIKE ?
                        OR data_categories LIKE ? OR owner LIKE ?)""")
        params += [f"%{q}%"] * 4
    if basis in LEGAL_BASES:
        where.append("legal_basis = ?")
        params.append(basis)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY system_name COLLATE NOCASE"

    rows = db.execute(sql, params).fetchall()
    return render_template("registry.html", entries=rows, q=q, basis=basis,
                           legal_bases=LEGAL_BASES)


@app.route("/registry/create", methods=["POST"])
@role_required("DPO", "Admin")
@audited("CREATE")
def registry_create():
    fields = ["system_name", "purpose", "data_categories",
              "legal_basis", "retention_period", "owner"]
    values = {f: request.form.get(f, "").strip() for f in fields}
    if not all(values.values()) or values["legal_basis"] not in LEGAL_BASES:
        flash("All registry fields are required (with a valid legal basis).", "error")
        return redirect(url_for("registry"))
    db = get_db()
    cur = db.execute(
        """INSERT INTO processing_registry
           (system_name, purpose, data_categories, legal_basis, retention_period, owner)
           VALUES (:system_name, :purpose, :data_categories, :legal_basis,
                   :retention_period, :owner)""",
        values,
    )
    db.commit()
    g.audit_payload = {"table": "processing_registry",
                       "record_id": cur.lastrowid, "record": values}
    flash(f"Registry entry “{values['system_name']}” created.", "success")
    return redirect(url_for("registry"))


@app.route("/registry/<int:rid>/delete", methods=["POST"])
@role_required("DPO", "Admin")
@audited("DELETE")
def registry_delete(rid):
    db = get_db()
    row = db.execute("SELECT * FROM processing_registry WHERE id = ?", (rid,)).fetchone()
    if row is None:
        flash("Registry entry not found.", "error")
        return redirect(url_for("registry"))
    db.execute("DELETE FROM processing_registry WHERE id = ?", (rid,))
    db.commit()
    g.audit_payload = {"table": "processing_registry", "record_id": rid,
                       "deleted_record": dict(row)}
    flash(f"Registry entry “{row['system_name']}” deleted.", "success")
    return redirect(url_for("registry"))


# ---------------------------------------------------------------------------
# System Audit Logs (Admin only) — read-only by design
# ---------------------------------------------------------------------------
@app.route("/audit")
@role_required("Admin")
def audit():
    db = get_db()
    q = request.args.get("q", "").strip()
    action = request.args.get("action", "").strip()

    sql = "SELECT * FROM audit_logs"
    where, params = [], []
    if q:
        where.append("(user_identity LIKE ? OR json_payload LIKE ? OR source_ip LIKE ?)")
        params += [f"%{q}%"] * 3
    if action:
        where.append("action_type = ?")
        params.append(action)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT 500"

    rows = db.execute(sql, params).fetchall()
    return render_template("audit.html", logs=rows, q=q, action=action)


# ---------------------------------------------------------------------------
# Export Endpoints (Reporting Module)
# ---------------------------------------------------------------------------
def _registry_rows():
    return get_db().execute(
        "SELECT * FROM processing_registry ORDER BY system_name COLLATE NOCASE"
    ).fetchall()


@app.route("/export/excel")
@role_required("DPO", "Admin")
@audited("EXPORT")
def export_excel():
    """CSV export — opens directly in Excel."""
    rows = _registry_rows()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "System Name", "Purpose", "Data Categories",
                     "Legal Basis", "Retention Period", "Process Owner", "Created"])
    for r in rows:
        writer.writerow([r["id"], r["system_name"], r["purpose"], r["data_categories"],
                         r["legal_basis"], r["retention_period"], r["owner"], r["created_at"]])
    g.audit_payload = {"export": "processing_registry.csv", "row_count": len(rows)}
    return Response(
        buf.getvalue().encode("utf-8-sig"),  # BOM so Excel detects UTF-8
        mimetype="text/csv",
        headers={"Content-Disposition":
                 f"attachment; filename=processing_registry_{datetime.now():%Y%m%d}.csv"},
    )


@app.route("/export/pdf")
@role_required("DPO", "Admin")
@audited("EXPORT")
def export_pdf():
    """
    Print-ready compliance report (stdlib only, no PDF library).
    A dedicated HTML report page opens and triggers the browser's native
    "Save as PDF" dialog — producing a real, formatted PDF file.
    """
    rows = _registry_rows()
    g.audit_payload = {"export": "processing_registry.pdf", "row_count": len(rows)}
    return render_template("report_pdf.html", entries=rows,
                           generated=datetime.now().strftime("%B %d, %Y %H:%M"),
                           generated_by=session["name"])


# ---------------------------------------------------------------------------
# JSON search APIs (used by the live-filter JS, also directly callable)
# ---------------------------------------------------------------------------
@app.route("/api/search/registry")
@role_required("DPO", "Admin")
def api_search_registry():
    q = request.args.get("q", "").strip()
    rows = get_db().execute(
        """SELECT * FROM processing_registry
           WHERE system_name LIKE ? OR purpose LIKE ? OR data_categories LIKE ?
           ORDER BY system_name""",
        (f"%{q}%", f"%{q}%", f"%{q}%"),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/search/consents")
@login_required
def api_search_consents():
    q = request.args.get("q", "").strip()
    sql = """SELECT c.*, u.name AS owner_name FROM consents c
             JOIN users u ON u.id = c.user_id
             WHERE (c.touchpoint_name LIKE ? OR u.name LIKE ?)"""
    params = [f"%{q}%", f"%{q}%"]
    if session["role"] == "User":
        sql += " AND c.user_id = ?"
        params.append(session["user_id"])
    rows = get_db().execute(sql + " ORDER BY c.timestamp DESC", params).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
