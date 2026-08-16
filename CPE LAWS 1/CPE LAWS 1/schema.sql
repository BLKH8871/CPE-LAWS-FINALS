-- Data Privacy Compliance Management System - Final Schema

-- This file should be idempotent, meaning it can be run multiple times without causing errors.
-- DROP statements are placed at the beginning to ensure a clean slate on re-initialization.

DROP TABLE IF EXISTS consents;
DROP TABLE IF EXISTS dsr_requests;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS processing_registry;
DROP TABLE IF EXISTS privacy_notices;
DROP TABLE IF EXISTS personal_data_inventory;
DROP TABLE IF EXISTS compliance_checklist;
DROP TABLE IF EXISTS users;


-- Core Tables
-- 'users' must be created first due to foreign key constraints in other tables.

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    -- Role determines the user's access level: 'Admin', 'DPO', 'User'
    role TEXT NOT NULL CHECK(role IN ('Admin', 'DPO', 'User'))
);

CREATE TABLE consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    touchpoint_name TEXT NOT NULL, -- The specific service or process for which consent is given.
    status TEXT NOT NULL CHECK(status IN ('Active', 'Pending', 'Revoked')),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE dsr_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    request_type TEXT NOT NULL CHECK(request_type IN ('Access', 'Rectification', 'Erasure', 'Restriction', 'Portability', 'Objection')),
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Pending', 'Under Review', 'Approved', 'Denied', 'Completed')) DEFAULT 'Pending',
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,
    resolution_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);


-- DPO & Admin Management Tables

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_identity TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK(action_type IN ('CREATE', 'READ', 'UPDATE', 'DELETE', 'LOGIN', 'LOGOUT', 'EXPORT')),
    source_ip TEXT,
    description TEXT,
    json_payload TEXT -- Stores a JSON object of the data that was changed.
);

CREATE TABLE processing_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    data_categories TEXT NOT NULL,
    legal_basis TEXT NOT NULL,
    retention_period TEXT NOT NULL,
    owner TEXT NOT NULL
);

CREATE TABLE privacy_notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    is_published BOOLEAN NOT NULL DEFAULT 0,
    published_at DATETIME
);


-- Internal DPO Tooling Tables

CREATE TABLE personal_data_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_item TEXT NOT NULL,
    category TEXT NOT NULL,
    purpose TEXT NOT NULL,
    storage_location TEXT NOT NULL,
    data_type TEXT NOT NULL -- e.g., 'Operational', 'Marketing', 'Analytics', 'Security'
);

CREATE TABLE compliance_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Compliant', 'Non-Compliant', 'In-Progress')),
    notes TEXT,
    last_reviewed DATETIME DEFAULT CURRENT_TIMESTAMP
);
