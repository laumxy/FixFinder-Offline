-- ============================================================================
-- FixFinder Knowledge Library — Master Repair Schema
-- SQLite Database Schema
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: categories
-- ============================================================================
CREATE TABLE IF NOT EXISTS categories (
    category_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id      TEXT    NOT NULL,
    category_name   TEXT    NOT NULL,
    category_code   TEXT    NOT NULL UNIQUE,
    description     TEXT,
    total_systems   INTEGER DEFAULT 0,
    total_symptoms  INTEGER DEFAULT 0,
    total_repairs   INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

-- ============================================================================
-- TABLE: subcategories
-- ============================================================================
CREATE TABLE IF NOT EXISTS subcategories (
    subcategory_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id      INTEGER NOT NULL,
    subcategory_name TEXT    NOT NULL,
    subcategory_code TEXT    NOT NULL UNIQUE,
    description      TEXT,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: systems
-- ============================================================================
CREATE TABLE IF NOT EXISTS systems (
    system_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    subcategory_id            INTEGER NOT NULL,
    system_name               TEXT    NOT NULL,
    system_code               TEXT    NOT NULL UNIQUE,
    brand                     TEXT,
    model                     TEXT,
    year_released             INTEGER,
    lifespan_years            REAL,
    maintenance_interval_months INTEGER,
    specifications            JSON    DEFAULT '{}',
    components                JSON    DEFAULT '[]',
    parts_list                JSON    DEFAULT '[]',
    common_issues             JSON    DEFAULT '[]',
    created_at                TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (subcategory_id) REFERENCES subcategories(subcategory_id) ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: symptoms
-- ============================================================================
CREATE TABLE IF NOT EXISTS symptoms (
    symptom_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id               INTEGER NOT NULL,
    category_id             INTEGER NOT NULL,
    symptom_name            TEXT    NOT NULL,
    symptom_code            TEXT    NOT NULL UNIQUE,
    severity                TEXT    NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical', 'Variable')),
    description             TEXT,
    common_causes           JSON    DEFAULT '[]',
    diagnostic_time_minutes INTEGER,
    difficulty              TEXT    NOT NULL CHECK (difficulty IN ('Easy', 'Moderate', 'Hard', 'Expert', 'Variable')),
    parts_needed            JSON    DEFAULT '[]',
    tools_needed            JSON    DEFAULT '[]',
    created_at              TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (system_id)   REFERENCES systems(system_id)     ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: diagnostic_trees
-- ============================================================================
CREATE TABLE IF NOT EXISTS diagnostic_trees (
    tree_id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    symptom_id                 INTEGER NOT NULL,
    tree_name                  TEXT    NOT NULL,
    tree_code                  TEXT    NOT NULL UNIQUE,
    steps                      JSON    DEFAULT '[]',
    decision_points            JSON    DEFAULT '[]',
    resolution_paths           JSON    DEFAULT '[]',
    total_steps                INTEGER DEFAULT 0,
    avg_resolution_time_minutes REAL,
    success_rate_percentage    REAL    DEFAULT 0.0,
    created_at                 TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (symptom_id) REFERENCES symptoms(symptom_id) ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: repair_procedures
-- ============================================================================
CREATE TABLE IF NOT EXISTS repair_procedures (
    repair_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tree_id                INTEGER NOT NULL,
    system_id              INTEGER NOT NULL,
    repair_name            TEXT    NOT NULL,
    repair_code            TEXT    NOT NULL UNIQUE,
    overview               TEXT,
    tools_required         JSON    DEFAULT '[]',
    materials_required     JSON    DEFAULT '[]',
    pre_repair_checks      JSON    DEFAULT '[]',
    procedure_steps        JSON    DEFAULT '[]',
    post_repair_checks     JSON    DEFAULT '[]',
    estimated_time_minutes INTEGER,
    difficulty             TEXT    NOT NULL CHECK (difficulty IN ('Easy', 'Moderate', 'Hard', 'Expert')),
    warnings               JSON    DEFAULT '[]',
    safety_notes           TEXT,
    created_at             TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (tree_id)   REFERENCES diagnostic_trees(tree_id) ON DELETE CASCADE,
    FOREIGN KEY (system_id) REFERENCES systems(system_id)        ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: parts_inventory
-- ============================================================================
CREATE TABLE IF NOT EXISTS parts_inventory (
    part_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    part_name            TEXT    NOT NULL,
    part_code            TEXT    NOT NULL UNIQUE,
    compatible_systems   JSON    DEFAULT '[]',
    average_cost         DECIMAL(10, 2) DEFAULT 0.00,
    current_stock        INTEGER DEFAULT 0,
    reorder_level        INTEGER DEFAULT 0,
    supplier             TEXT,
    supplier_contact     TEXT,
    lead_time_days       INTEGER,
    unit                 TEXT    DEFAULT 'piece',
    coverage             TEXT,
    category_id          INTEGER,
    created_at           TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE SET NULL
);

-- ============================================================================
-- TABLE: embeddings
-- ============================================================================
CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type      TEXT    NOT NULL CHECK (entity_type IN ('system', 'symptom', 'repair', 'part')),
    entity_id        INTEGER NOT NULL,
    embedding_vector BLOB,
    embedding_text   TEXT,
    created_at       TEXT    DEFAULT (datetime('now')),
    UNIQUE (entity_type, entity_id)
);

-- ============================================================================
-- TABLE: faiss_metadata
-- ============================================================================
CREATE TABLE IF NOT EXISTS faiss_metadata (
    index_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id     TEXT    NOT NULL,
    dimension      INTEGER DEFAULT 768,
    index_type     TEXT    DEFAULT 'HNSW32',
    total_entries  INTEGER DEFAULT 0,
    index_path     TEXT,
    created_at     TEXT    DEFAULT (datetime('now')),
    mapping        JSON    DEFAULT '{}'
);

-- ============================================================================
-- TABLE: repair_records
-- ============================================================================
CREATE TABLE IF NOT EXISTS repair_records (
    record_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_id              INTEGER NOT NULL,
    system_id              INTEGER NOT NULL,
    symptom_id             INTEGER NOT NULL,
    repair_date            TEXT    NOT NULL DEFAULT (date('now')),
    technician_name        TEXT,
    technician_rating      INTEGER CHECK (technician_rating BETWEEN 1 AND 5),
    repair_duration_minutes INTEGER,
    parts_used             JSON    DEFAULT '[]',
    total_cost             DECIMAL(10, 2) DEFAULT 0.00,
    outcome                TEXT    NOT NULL CHECK (outcome IN ('Successful', 'Partial', 'Failed', 'Deferred')),
    notes                  TEXT,
    follow_up_needed       BOOLEAN DEFAULT 0,
    FOREIGN KEY (repair_id)  REFERENCES repair_procedures(repair_id) ON DELETE CASCADE,
    FOREIGN KEY (system_id)  REFERENCES systems(system_id)           ON DELETE CASCADE,
    FOREIGN KEY (symptom_id) REFERENCES symptoms(symptom_id)        ON DELETE CASCADE
);

-- ============================================================================
-- TABLE: validation_results
-- ============================================================================
CREATE TABLE IF NOT EXISTS validation_results (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id    TEXT    NOT NULL,
    test_name     TEXT    NOT NULL,
    test_type     TEXT,
    passed        BOOLEAN NOT NULL DEFAULT 0,
    details       TEXT,
    run_date      TEXT    DEFAULT (datetime('now'))
);

-- ============================================================================
-- TABLE: ai_prompts
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_prompts (
    prompt_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_name  TEXT    NOT NULL,
    prompt_type  TEXT    NOT NULL CHECK (prompt_type IN ('diagnostic', 'repair', 'search', 'recommendation')),
    template     TEXT    NOT NULL,
    version_id   TEXT    NOT NULL,
    created_at   TEXT    DEFAULT (datetime('now'))
);

-- ============================================================================
-- INDEXES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_systems_category    ON systems(subcategory_id);
CREATE INDEX IF NOT EXISTS idx_symptoms_system     ON symptoms(system_id);
CREATE INDEX IF NOT EXISTS idx_symptoms_category   ON symptoms(category_id);
CREATE INDEX IF NOT EXISTS idx_diagnostic_symptom  ON diagnostic_trees(symptom_id);
CREATE INDEX IF NOT EXISTS idx_repairs_tree        ON repair_procedures(tree_id);
CREATE INDEX IF NOT EXISTS idx_repairs_system      ON repair_procedures(system_id);
CREATE INDEX IF NOT EXISTS idx_parts_category      ON parts_inventory(category_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_entity   ON embeddings(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_repair_records_date ON repair_records(repair_date);
CREATE INDEX IF NOT EXISTS idx_records_system      ON repair_records(system_id);

-- ============================================================================
-- VIEW: v_system_full
-- Full system view with category and subcategory context
-- ============================================================================
CREATE VIEW IF NOT EXISTS v_system_full AS
SELECT
    s.system_id,
    s.system_code,
    s.system_name,
    s.brand,
    s.model,
    s.year_released,
    s.lifespan_years,
    s.maintenance_interval_months,
    s.specifications,
    s.components,
    s.parts_list,
    s.common_issues,
    sc.subcategory_id,
    sc.subcategory_name,
    sc.subcategory_code,
    c.category_id,
    c.category_name,
    c.category_code,
    c.version_id,
    s.created_at
FROM systems s
JOIN subcategories sc ON s.subcategory_id = sc.subcategory_id
JOIN categories c      ON sc.category_id  = c.category_id;

-- ============================================================================
-- VIEW: v_symptom_diagnostic
-- Symptom view linked to diagnostic trees and system context
-- ============================================================================
CREATE VIEW IF NOT EXISTS v_symptom_diagnostic AS
SELECT
    sym.symptom_id,
    sym.symptom_code,
    sym.symptom_name,
    sym.severity,
    sym.description,
    sym.common_causes,
    sym.diagnostic_time_minutes,
    sym.difficulty,
    sym.parts_needed,
    sym.tools_needed,
    s.system_name,
    s.system_code,
    s.brand,
    s.model,
    c.category_name,
    c.category_code,
    dt.tree_id,
    dt.tree_name,
    dt.tree_code,
    dt.total_steps,
    dt.avg_resolution_time_minutes,
    dt.success_rate_percentage,
    sym.created_at
FROM symptoms sym
JOIN systems s          ON sym.system_id   = s.system_id
JOIN categories c       ON sym.category_id = c.category_id
LEFT JOIN diagnostic_trees dt ON dt.symptom_id = sym.symptom_id;

-- ============================================================================
-- VIEW: v_repair_complete
-- Complete repair view with procedure, system, and tree context
-- ============================================================================
CREATE VIEW IF NOT EXISTS v_repair_complete AS
SELECT
    rp.repair_id,
    rp.repair_code,
    rp.repair_name,
    rp.overview,
    rp.tools_required,
    rp.materials_required,
    rp.pre_repair_checks,
    rp.procedure_steps,
    rp.post_repair_checks,
    rp.estimated_time_minutes,
    rp.difficulty,
    rp.warnings,
    rp.safety_notes,
    dt.tree_name,
    dt.tree_code,
    s.system_name,
    s.system_code,
    s.brand,
    s.model,
    sc.subcategory_name,
    c.category_name,
    c.category_code,
    rp.created_at
FROM repair_procedures rp
JOIN diagnostic_trees dt ON rp.tree_id   = dt.tree_id
JOIN systems s           ON rp.system_id = s.system_id
JOIN subcategories sc    ON s.subcategory_id = sc.subcategory_id
JOIN categories c        ON sc.category_id   = c.category_id;

-- ============================================================================
-- VIEW: v_parts_availability
-- Parts view with stock status and category context
-- ============================================================================
CREATE VIEW IF NOT EXISTS v_parts_availability AS
SELECT
    pi.part_id,
    pi.part_code,
    pi.part_name,
    pi.compatible_systems,
    pi.average_cost,
    pi.current_stock,
    pi.reorder_level,
    CASE
        WHEN pi.current_stock <= 0 THEN 'Out of Stock'
        WHEN pi.current_stock <= pi.reorder_level THEN 'Low Stock'
        ELSE 'In Stock'
    END AS stock_status,
    pi.supplier,
    pi.supplier_contact,
    pi.lead_time_days,
    pi.unit,
    pi.coverage,
    c.category_name,
    c.category_code,
    pi.created_at
FROM parts_inventory pi
LEFT JOIN categories c ON pi.category_id = c.category_id;
