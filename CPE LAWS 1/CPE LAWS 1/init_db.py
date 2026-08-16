import sqlite3
from werkzeug.security import generate_password_hash

# Define the database file name
DATABASE = 'C:/Users/jmbri/Documents/CPE LAWS 1/compliance_system.db'

# SQL statements to create tables
TABLES = {
    "users": """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('User', 'DPO', 'Admin'))
        );
    """,
    "audit_logs": """
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_identity TEXT,
            action_type TEXT NOT NULL,
            source_ip TEXT,
            description TEXT,
            json_payload TEXT
        );
    """,
    "consents": """
        CREATE TABLE consents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            touchpoint_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Active', 'Revoked')),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """,
    "dsr_requests": """
        CREATE TABLE dsr_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            request_type TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME,
            resolution_notes TEXT,
            proof_document TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """,
    "processing_registry": """
        CREATE TABLE processing_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_name TEXT NOT NULL,
            purpose TEXT,
            data_categories TEXT,
            legal_basis TEXT,
            retention_period TEXT,
            owner TEXT
        );
    """,
    "personal_data_inventory": """
        CREATE TABLE personal_data_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            data_item TEXT NOT NULL,
            category TEXT,
            location TEXT,
            purpose TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """,
    "compliance_checklist": """
        CREATE TABLE compliance_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement TEXT NOT NULL,
            status TEXT DEFAULT 'Not Started',
            notes TEXT
        );
    """,
    "privacy_notices": """
        CREATE TABLE privacy_notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            version TEXT NOT NULL,
            content TEXT,
            updated_at DATETIME,
            published_at DATETIME,
            is_published BOOLEAN DEFAULT 0
        );
    """
}

# Standard set of DSR request types (GDPR/DPA rights)
DSR_TYPES = [
    'Access', 'Rectification', 'Erasure', 'Restriction', 'Portability', 'Objection'
]

# Seed users: (name, email, password, role)
SEED_USERS = [
    ('Admin User', 'admin@example.com', 'admin', 'Admin'),
    ('DPO User', 'dpo@example.com', 'dpo', 'DPO'),
    ('John Doe', 'user@example.com', 'user', 'User'),
]


def initialize_database():
    """Connects to the database and creates all tables if they don't exist."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print("Successfully connected to the database.")

        for table_name, create_sql in TABLES.items():
            try:
                print(f"Creating table: {table_name}...")
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                cursor.execute(create_sql)
                print(f"Table '{table_name}' created successfully.")
            except sqlite3.Error as e:
                print(f"Error creating table {table_name}: {e}")

        conn.commit()
        print("Database initialization complete. All tables created.")

        # Seed users (idempotent by email via INSERT OR IGNORE)
        user_ids = {}
        print("Seeding users...")
        for name, email, password, role in SEED_USERS:
            try:
                password_hash = generate_password_hash(password)
                cursor.execute(
                    "INSERT OR IGNORE INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                    (name, email, password_hash, role)
                )
                conn.commit()
                # Fetch the id (whether inserted now or pre-existing)
                row = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                user_ids[email] = row['id'] if row else None
                print(f"User '{email}' ready.")
            except Exception as e:
                print(f"Error seeding user {email}: {e}")

        # Add Mock Data
        print("Adding mock data...")
        try:
            # Mock Processing Registry
            cursor.execute("INSERT INTO processing_registry (system_name, purpose, owner) VALUES (?, ?, ?)",
                           ('Marketing CRM', 'To manage customer relationships and send marketing emails.', 'Marketing Dept'))
            cursor.execute("INSERT INTO processing_registry (system_name, purpose, owner) VALUES (?, ?, ?)",
                           ('HR Payroll System', 'To process employee salaries and benefits.', 'HR Dept'))

            # Mock Personal Data Inventory (linked to specific users)
            admin_id = user_ids.get('admin@example.com')
            dpo_id = user_ids.get('dpo@example.com')
            user_id = user_ids.get('user@example.com')

            # Admin's data
            cursor.execute("INSERT INTO personal_data_inventory (user_id, data_item, category, location, purpose) VALUES (?, ?, ?, ?, ?)",
                           (admin_id, 'Customer Email', 'Contact Info', 'Marketing CRM', 'Marketing communications'))
            # DPO's data
            cursor.execute("INSERT INTO personal_data_inventory (user_id, data_item, category, location, purpose) VALUES (?, ?, ?, ?, ?)",
                           (dpo_id, 'Employee Salary', 'Financial', 'HR Payroll System', 'Payroll processing'))
            # Regular User's data
            cursor.execute("INSERT INTO personal_data_inventory (user_id, data_item, category, location, purpose) VALUES (?, ?, ?, ?, ?)",
                           (user_id, 'Phone Number', 'Contact Info', 'Marketing CRM', 'Marketing communications'))
            cursor.execute("INSERT INTO personal_data_inventory (user_id, data_item, category, location, purpose) VALUES (?, ?, ?, ?, ?)",
                           (user_id, 'Home Address', 'Contact Info', 'Order Fulfillment System', 'Delivery of orders'))
            cursor.execute("INSERT INTO personal_data_inventory (user_id, data_item, category, location, purpose) VALUES (?, ?, ?, ?, ?)",
                           (user_id, 'Purchase History', 'Transaction', 'E-commerce Platform', 'Order history and recommendations'))

            # Mock Compliance Checklist
            cursor.execute("INSERT INTO compliance_checklist (requirement, status) VALUES (?, ?)",
                           ('Conduct Data Protection Impact Assessment (DPIA) for new projects.', 'In Progress'))
            cursor.execute("INSERT INTO compliance_checklist (requirement, status) VALUES (?, ?)",
                           ('Review and update privacy policy annually.', 'Completed'))

            # Mock Consents
            cursor.execute("INSERT INTO consents (user_id, touchpoint_name, status) VALUES (?, ?, ?)",
                           (admin_id, 'Newsletter Signup', 'Active'))
            cursor.execute("INSERT INTO consents (user_id, touchpoint_name, status) VALUES (?, ?, ?)",
                           (dpo_id, 'Product Update Emails', 'Revoked'))
            # User's consents
            cursor.execute("INSERT INTO consents (user_id, touchpoint_name, status) VALUES (?, ?, ?)",
                           (user_id, 'Newsletter Signup', 'Active'))
            cursor.execute("INSERT INTO consents (user_id, touchpoint_name, status) VALUES (?, ?, ?)",
                           (user_id, 'Marketing SMS', 'Revoked'))

            # Mock DSR Requests (one per user so pages have content)
            cursor.execute("INSERT INTO dsr_requests (user_id, request_type, status) VALUES (?, ?, ?)",
                           (admin_id, 'Data Portability', 'Pending'))
            cursor.execute("INSERT INTO dsr_requests (user_id, request_type, status) VALUES (?, ?, ?)",
                           (dpo_id, 'Right to Erasure', 'Resolved'))
            cursor.execute("INSERT INTO dsr_requests (user_id, request_type, status) VALUES (?, ?, ?)",
                           (user_id, 'Access', 'Pending'))

            # Mock published privacy notice so the User page has content
            cursor.execute("""
                INSERT INTO privacy_notices (title, version, content, updated_at, published_at, is_published)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            """, ('Privacy Policy', '1.0',
                  '<p>We collect and process your personal data in accordance with applicable data protection laws.</p>'))

            conn.commit()
            print("Mock data added successfully.")
        except Exception as e:
            print(f"Error adding mock data: {e}")

    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


if __name__ == '__main__':
    initialize_database()
