-- ============================================================================
--  Data Privacy Compliance Management System (DPCMS)
--  RA 10173 (Philippine Data Privacy Act of 2012) Compliance Portal
--  SQLite3 Schema
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. USERS  (System Administrator / Data Protection Officer / Regular Employee)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('Admin', 'DPO', 'User')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ----------------------------------------------------------------------------
-- 2. CONSENTS  (Consent lifecycle per data-collection touchpoint)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS consents;
CREATE TABLE consents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    touchpoint_name TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'Pending'
                            CHECK (status IN ('Active', 'Pending', 'Revoked')),
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_consents_user   ON consents(user_id);
CREATE INDEX idx_consents_status ON consents(status);

-- ----------------------------------------------------------------------------
-- 3. PROCESSING REGISTRY  (Records of Processing Activities - NPC inventory)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS processing_registry;
CREATE TABLE processing_registry (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name      TEXT NOT NULL,
    purpose          TEXT NOT NULL,
    data_categories  TEXT NOT NULL,
    legal_basis      TEXT NOT NULL CHECK (legal_basis IN
                        ('Consent', 'Contract', 'Legal Obligation',
                         'Vital Interest', 'Public Task', 'Legitimate Interest')),
    retention_period TEXT NOT NULL,
    owner            TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX idx_registry_system ON processing_registry(system_name);

-- ----------------------------------------------------------------------------
-- 4. AUDIT LOGS  (Permanent, immutable trail for NPC inspection)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS audit_logs;
CREATE TABLE audit_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    user_identity TEXT NOT NULL,
    action_type   TEXT NOT NULL CHECK (action_type IN
                     ('CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'EXPORT')),
    source_ip     TEXT NOT NULL,
    json_payload  TEXT NOT NULL
);

CREATE INDEX idx_audit_time   ON audit_logs(timestamp);
CREATE INDEX idx_audit_action ON audit_logs(action_type);

-- Immutability guarantee: the database itself rejects any UPDATE or DELETE
-- on audit rows, so the trail cannot be tampered with even by direct SQL.
CREATE TRIGGER audit_logs_no_update
BEFORE UPDATE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'Audit logs are immutable (RA 10173 accountability).');
END;

CREATE TRIGGER audit_logs_no_delete
BEFORE DELETE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'Audit logs are immutable (RA 10173 accountability).');
END;
