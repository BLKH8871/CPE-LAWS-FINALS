# D:/school/CPE LAWS/database.py
import sqlite3
from werkzeug.security import generate_password_hash

# --- Configuration ---
DATABASE_FILE = 'compliance_system.db'
SCHEMA_FILE = 'schema.sql'

def initialize_database():
    """
    Initializes the database by creating tables from schema.sql and populating it with seed data.
    """
    print("Connecting to the database...")
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    print(f"Executing schema from {SCHEMA_FILE}...")
    with open(SCHEMA_FILE, 'r') as f:
        cursor.executescript(f.read())
    print("Tables created successfully.")

    # --- Seed Data ---
    print("Inserting seed data...")

    # 1. Users (Admin, DPO, Regular User)
    users_to_add = [
        (
            'System Administrator',
            'admin@dpcms.com',
            generate_password_hash('AdminPass123!'),
            'Admin'
        ),
        (
            'Data Protection Officer',
            'dpo@dpcms.com',
            generate_password_hash('DpoPass123!'),
            'DPO'
        ),
        (
            'John Doe',
            'john.doe@example.com',
            generate_password_hash('UserPass123!'),
            'User'
        ),
        (
            'Juan Dela Cruz',
            'juan.cruz@example.com',
            generate_password_hash('UserPass123!'),
            'User'
        )
    ]
    cursor.executemany('INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)', users_to_add)
    print(f"{len(users_to_add)} users added.")

    # 2. Consents for the regular users
    user_id_john = 3
    dpo_id = 2
    user_id_juan = 4
    consents_to_add = [
        (user_id_john, 'Marketing Newsletter Subscription', 'Active'),
        (user_id_john, 'Third-Party Analytics Tracking', 'Active'),
        (user_id_john, 'Product Update Notifications', 'Revoked'),
        (user_id_juan, 'HRIS Employee File Tracking', 'Active'),
        (user_id_juan, 'Marketing Email Hub', 'Revoked')
    ]
    cursor.executemany('INSERT INTO consents (user_id, touchpoint_name, status) VALUES (?, ?, ?)', consents_to_add)
    print(f"{len(consents_to_add)} consent records added.")

    # 3. Processing Registry Entries
    registry_entries = [
        (
            'HR Information System',
            'To manage employee payroll and benefits.',
            'PII: Name, Address, Contact Info | Sensitive Personal Info: Bank Details, Government ID Numbers',
            'Employment Contract',
            '7 years after employment cessation',
            'HR Department'
        ),
        (
            'Customer Relationship Management (CRM)',
            'To track sales leads and customer interactions.',
            'PII: Name, Email, Phone Number, Company, Interaction History',
            'Legitimate Interest',
            '3 years after last contact',
            'Sales Department'
        ),
        (
            'Website Analytics Platform',
            'To monitor website traffic and user behavior for service improvement.',
            'PII: IP Address, Browser Type, Pages Visited, Session Duration',
            'Consent',
            '26 months',
            'Marketing Department'
        )
    ]
    cursor.executemany('INSERT INTO processing_registry (system_name, purpose, data_categories, legal_basis, retention_period, owner) VALUES (?, ?, ?, ?, ?, ?)', registry_entries)
    print(f"{len(registry_entries)} processing registry entries added.")

    # 4. Privacy Notices
    privacy_notices_to_add = [
        ('Website Privacy Policy', '1.0.0', 'This privacy policy explains how our company collects, uses, and protects your personal data when you visit our website.', 1, '2026-07-10 11:00:00'),
        ('Employee Data Handling Policy', '1.1.0', 'This internal policy outlines the procedures for handling employee data in compliance with the Data Privacy Act.', 0, None)
    ]
    cursor.executemany('INSERT INTO privacy_notices (title, version, content, is_published, published_at) VALUES (?, ?, ?, ?, ?)', privacy_notices_to_add)
    print(f"{len(privacy_notices_to_add)} privacy notices added.")

    # 5. DSR
    user_id_john = 3
    dsr_requests_to_add = [
        (user_id_john, 'Access', 'Please provide a copy of all personal data you hold about me.', 'Pending', None, None),
        (user_id_john, 'Erasure', 'I request the deletion of my account and all associated data.', 'Under Review', None, 'Investigating data retention obligations under RA 10173.')
    ]
    cursor.executemany('INSERT INTO dsr_requests (user_id, request_type, description, status, resolved_at, resolution_notes) VALUES (?, ?, ?, ?, ?, ?)', dsr_requests_to_add)
    print(f"{len(dsr_requests_to_add)} DSR added.")

    # 6. Incidents (REMOVED)

    # 7. Audit Logs
    audit_logs_to_add = [
        ('System (Seed)', 'CREATE', '127.0.0.1', 'Created user: System Administrator', '{"role": "Admin"}'),
        ('System (Seed)', 'CREATE', '127.0.0.1', 'Created user: Data Protection Officer', '{"role": "DPO"}'),
        ('System (Seed)', 'CREATE', '127.0.0.1', 'Created user: John Doe', '{"role": "User"}'),
        ('Data Protection Officer (DPO)', 'LOGIN', '192.168.1.10', "User 'Data Protection Officer' logged in successfully.", '{}'),
        ('Data Protection Officer (DPO)', 'UPDATE', '192.168.1.10', "Updated incident ID 2 with status 'Under Investigation'.", '{"incident_id": 2, "status": "Under Investigation"}'),
        ('John Doe (User)', 'CREATE', '203.0.113.25', 'Reported a new security incident: A visitor found a broken link on our public privacy policy page.', '{"severity": "Low"}'),
        ('John Doe (User)', 'LOGIN', '203.0.113.25', "User 'John Doe' logged in successfully.", '{}'),
        ('John Doe (User)', 'LOGOUT', '203.0.113.25', "User 'John Doe' logged out.", '{}')
    ]
    cursor.executemany('INSERT INTO audit_logs (user_identity, action_type, source_ip, description, json_payload) VALUES (?, ?, ?, ?, ?)', audit_logs_to_add)
    print(f"{len(audit_logs_to_add)} audit log records added.")

    # 8. Personal Data Inventory
    inventory_to_add = [
        ('User Email Address', 'PII', 'Authentication and Communication', 'User Database (EU)', 'Operational'),
        ('User IP Address', 'PII', 'Security and Analytics', 'Server Logs (US)', 'Security'),
        ('User Name', 'PII', 'Personalization', 'User Database (EU)', 'Operational'),
        ('User Health Data', 'Sensitive Personal Info', 'Fitness Tracking', 'Encrypted Health Database (EU)', 'Operational'),
        ('User Phone Number', 'PII', 'Communication', 'Mobile Network (US)', 'Operational'),
        ('User Location Data', 'PII', 'Geolocation Services', 'Cloud Storage (EU)', 'Marketing'),
        ('User Payment Information', 'Financial', 'E-commerce Processing', 'Encrypted Payment Gateway', 'Operational'),
        ('User Device Information', 'Technical', 'System Administration', 'Cloud Infrastructure (US)', 'Security'),
        ('User Social Security Number', 'Sensitive Personal Info', 'Compliance', 'Secure Database (EU)', 'Legal'),
        ('User Biometric Data', 'Sensitive Personal Info', 'Security Authentication', 'Encrypted Biometrics Database', 'Security')
    ]
    cursor.executemany('INSERT INTO personal_data_inventory (data_item, category, purpose, storage_location, data_type) VALUES (?, ?, ?, ?, ?)', inventory_to_add)
    print(f"{len(inventory_to_add)} personal data inventory records added.")

    # 9. Compliance Checklist
    checklist_to_add = [
        ('Data Processing Agreements (DPAs) in place with all third-party vendors.', 'Compliant', 'All major vendors covered.'),
        ('Regular data protection training for all employees.', 'In-Progress', 'Training scheduled for Q3.'),
        ('Privacy Impact Assessments (PIAs) conducted for all new projects.', 'Compliant', 'No new projects in Q2.'),
        ('Data retention policies are being enforced.', 'Non-Compliant', 'Legacy data needs to be purged.')
    ]
    cursor.executemany('INSERT INTO compliance_checklist (item, status, notes) VALUES (?, ?, ?)', checklist_to_add)
    print(f"{len(checklist_to_add)} compliance checklist records added.")


    # Commit changes and close connection
    conn.commit()
    conn.close()
    print("Database initialization complete. The 'compliance_system.db' file is ready.")

if __name__ == '__main__':
    initialize_database()
