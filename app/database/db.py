import json
import sqlite3
from pathlib import Path
from typing import Any

from app.database.models import KnowledgeProblem
from fixfinder_engine.config import settings

# ── Core knowledge schema ─────────────────────────────────────────────────────
_SCHEMA_CORE = """
CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    problem TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    symptoms TEXT NOT NULL,
    causes TEXT NOT NULL,
    inspection_steps TEXT NOT NULL,
    repair_steps TEXT NOT NULL,
    tools TEXT NOT NULL,
    safety TEXT NOT NULL,
    prevention TEXT NOT NULL,
    maintenance TEXT NOT NULL DEFAULT '[]',
    difficulty TEXT NOT NULL DEFAULT 'moderate',
    risk_level TEXT NOT NULL DEFAULT 'medium',
    estimated_time TEXT NOT NULL DEFAULT 'unknown',
    estimated_cost TEXT NOT NULL DEFAULT 'unknown',
    source_type TEXT NOT NULL DEFAULT 'seed',
    source_url TEXT NOT NULL DEFAULT '',
    reliability_score REAL NOT NULL DEFAULT 1.0,
    confidence_score REAL NOT NULL DEFAULT 1.0,
    knowledge_version TEXT NOT NULL DEFAULT 'v1.0',
    search_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, problem)
);
CREATE INDEX IF NOT EXISTS idx_problems_category ON problems(category);
CREATE INDEX IF NOT EXISTS idx_problems_problem ON problems(problem);
CREATE INDEX IF NOT EXISTS idx_problems_risk_level ON problems(risk_level);
CREATE INDEX IF NOT EXISTS idx_problems_knowledge_version ON problems(knowledge_version);

CREATE TABLE IF NOT EXISTS knowledge_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    record_count INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS problem_search USING fts5(
    problem, category, search_text,
    content='problems', content_rowid='id'
);
"""

# ── Licensing schema ──────────────────────────────────────────────────────────
_SCHEMA_LICENSING = """
CREATE TABLE IF NOT EXISTS licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT NOT NULL UNIQUE,
    license_type TEXT NOT NULL DEFAULT 'personal',
    status TEXT NOT NULL DEFAULT 'active',
    owner_name TEXT NOT NULL DEFAULT '',
    owner_email TEXT NOT NULL DEFAULT '',
    organization_id INTEGER,
    features TEXT NOT NULL DEFAULT '[]',
    allowed_industries TEXT NOT NULL DEFAULT '[]',
    max_devices INTEGER NOT NULL DEFAULT 1,
    issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    activated_at TEXT,
    last_validated_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);

CREATE TABLE IF NOT EXISTS license_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_id INTEGER NOT NULL REFERENCES licenses(id),
    device_fingerprint TEXT NOT NULL,
    device_name TEXT NOT NULL DEFAULT '',
    registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(license_id, device_fingerprint)
);
"""

# ── Enterprise schema ─────────────────────────────────────────────────────────
_SCHEMA_ENTERPRISE = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    license_id INTEGER REFERENCES licenses(id),
    brand_config TEXT NOT NULL DEFAULT '{}',
    deployment_config TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'technician',
    organization_id INTEGER REFERENCES organizations(id),
    license_id INTEGER REFERENCES licenses(id),
    is_active INTEGER NOT NULL DEFAULT 1,
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);

CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    permissions TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT ''
);
"""

# ── Analytics schema ──────────────────────────────────────────────────────────
_SCHEMA_ANALYTICS = """
CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    problem TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0,
    language TEXT NOT NULL DEFAULT 'en',
    user_id INTEGER,
    organization_id INTEGER,
    knowledge_version TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_analytics_event_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_category ON analytics_events(category);
CREATE INDEX IF NOT EXISTS idx_analytics_created_at ON analytics_events(created_at);
"""

# ── Reporting schema ──────────────────────────────────────────────────────────
_SCHEMA_REPORTING = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL DEFAULT 'diagnostic',
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '{}',
    format TEXT NOT NULL DEFAULT 'json',
    file_path TEXT NOT NULL DEFAULT '',
    user_id INTEGER,
    organization_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);
"""

# ── Knowledge packaging schema ─────────────────────────────────────────────────
_SCHEMA_PACKAGING = """
CREATE TABLE IF NOT EXISTS knowledge_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    industries TEXT NOT NULL DEFAULT '[]',
    version TEXT NOT NULL DEFAULT '1.0',
    file_path TEXT NOT NULL DEFAULT '',
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    record_count INTEGER NOT NULL DEFAULT 0,
    installed INTEGER NOT NULL DEFAULT 0,
    installed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_packs_pack_id ON knowledge_packs(pack_id);
CREATE INDEX IF NOT EXISTS idx_packs_installed ON knowledge_packs(installed);
"""

# ── Localization schema ────────────────────────────────────────────────────────
_SCHEMA_LOCALIZATION = """
CREATE TABLE IF NOT EXISTS translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language_code TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(language_code, key)
);
CREATE INDEX IF NOT EXISTS idx_translations_lang ON translations(language_code);
"""

SCHEMA_SQL = (
    _SCHEMA_CORE
    + _SCHEMA_LICENSING
    + _SCHEMA_ENTERPRISE
    + _SCHEMA_ANALYTICS
    + _SCHEMA_REPORTING
    + _SCHEMA_PACKAGING
    + _SCHEMA_LOCALIZATION
)


# ── Connection helpers ─────────────────────────────────────────────────────────

def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize_schema(db_path: Path) -> None:
    with get_connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)


def reset_database(db_path: Path) -> None:
    with get_connection(db_path) as connection:
        connection.executescript("""
            DROP TABLE IF EXISTS translations;
            DROP TABLE IF EXISTS knowledge_packs;
            DROP TABLE IF EXISTS reports;
            DROP TABLE IF EXISTS analytics_events;
            DROP TABLE IF EXISTS roles;
            DROP TABLE IF EXISTS users;
            DROP TABLE IF EXISTS organizations;
            DROP TABLE IF EXISTS license_devices;
            DROP TABLE IF EXISTS licenses;
            DROP TABLE IF EXISTS problem_search;
            DROP TABLE IF EXISTS knowledge_versions;
            DROP TABLE IF EXISTS problems;
        """)
        connection.executescript(SCHEMA_SQL)


def _migrate_schema(db_path: Path) -> None:
    """Apply incremental column additions for schema upgrades (idempotent)."""
    migrations = [
        "ALTER TABLE problems ADD COLUMN maintenance TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE problems ADD COLUMN estimated_cost TEXT NOT NULL DEFAULT 'unknown'",
        "ALTER TABLE problems ADD COLUMN search_text TEXT NOT NULL DEFAULT ''",
    ]
    with get_connection(db_path) as conn:
        for sql in migrations:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists


def ensure_database(db_path: Path) -> dict[str, Any]:
    """Initialize schema if not present; apply migrations; return status dict."""
    existed = db_path.exists()
    initialize_schema(db_path)
    _migrate_schema(db_path)
    with get_connection(db_path) as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0])
    return {"existed": existed, "problem_count": count}


# ── Knowledge problem helpers ──────────────────────────────────────────────────

def insert_problem(connection: sqlite3.Connection, problem: KnowledgeProblem) -> int:
    cursor = connection.execute(
        """
        INSERT INTO problems (
            category, problem, aliases, symptoms, causes,
            inspection_steps, repair_steps, tools, safety, prevention,
            maintenance, difficulty, risk_level, estimated_time, estimated_cost,
            source_type, source_url, reliability_score, confidence_score,
            knowledge_version, search_text
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            problem.category, problem.problem,
            json.dumps(problem.aliases, ensure_ascii=False),
            json.dumps(problem.symptoms, ensure_ascii=False),
            json.dumps(problem.causes, ensure_ascii=False),
            json.dumps(problem.inspection_steps, ensure_ascii=False),
            json.dumps(problem.repair_steps, ensure_ascii=False),
            json.dumps(problem.tools, ensure_ascii=False),
            json.dumps(problem.safety, ensure_ascii=False),
            json.dumps(problem.prevention, ensure_ascii=False),
            json.dumps(getattr(problem, "maintenance", []), ensure_ascii=False),
            problem.difficulty, problem.risk_level,
            problem.estimated_time,
            getattr(problem, "estimated_cost", "unknown"),
            problem.source_type, problem.source_url,
            problem.reliability_score, problem.confidence_score,
            problem.knowledge_version, problem.search_text(),
        ),
    )
    return int(cursor.lastrowid)


def upsert_problem(connection: sqlite3.Connection, problem: KnowledgeProblem) -> int:
    existing = connection.execute(
        "SELECT id FROM problems WHERE category=? AND problem=?",
        (problem.category, problem.problem),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE problems SET
                aliases=?, symptoms=?, causes=?, inspection_steps=?,
                repair_steps=?, tools=?, safety=?, prevention=?,
                maintenance=?, difficulty=?, risk_level=?, estimated_time=?,
                estimated_cost=?, source_type=?, source_url=?,
                reliability_score=?, confidence_score=?, knowledge_version=?,
                search_text=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                json.dumps(problem.aliases, ensure_ascii=False),
                json.dumps(problem.symptoms, ensure_ascii=False),
                json.dumps(problem.causes, ensure_ascii=False),
                json.dumps(problem.inspection_steps, ensure_ascii=False),
                json.dumps(problem.repair_steps, ensure_ascii=False),
                json.dumps(problem.tools, ensure_ascii=False),
                json.dumps(problem.safety, ensure_ascii=False),
                json.dumps(problem.prevention, ensure_ascii=False),
                json.dumps(getattr(problem, "maintenance", []), ensure_ascii=False),
                problem.difficulty, problem.risk_level,
                problem.estimated_time,
                getattr(problem, "estimated_cost", "unknown"),
                problem.source_type, problem.source_url,
                problem.reliability_score, problem.confidence_score,
                problem.knowledge_version, problem.search_text(),
                int(existing["id"]),
            ),
        )
        return int(existing["id"])
    return insert_problem(connection, problem)


def fetch_all_problem_records(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with get_connection(db_path) as connection:
        rows = connection.execute("SELECT * FROM problems").fetchall()
    records = []
    for row in rows:
        keys = row.keys()
        def _get(col, default=None):
            return row[col] if col in keys else default
        records.append({
            "id": row["id"],
            "category": row["category"],
            "problem": row["problem"],
            "aliases": json.loads(_get("aliases", "[]") or "[]"),
            "symptoms": json.loads(row["symptoms"]),
            "causes": json.loads(row["causes"]),
            "inspection_steps": json.loads(row["inspection_steps"]),
            "repair_steps": json.loads(row["repair_steps"]),
            "tools": json.loads(row["tools"]),
            "safety": json.loads(row["safety"]),
            "prevention": json.loads(row["prevention"]),
            "maintenance": json.loads(_get("maintenance", "[]") or "[]"),
            "difficulty": _get("difficulty", "moderate"),
            "risk_level": _get("risk_level", "medium"),
            "estimated_time": _get("estimated_time", "unknown"),
            "estimated_cost": _get("estimated_cost", "unknown"),
            "source_type": _get("source_type", "seed"),
            "source_url": _get("source_url", ""),
            "reliability_score": _get("reliability_score", 1.0),
            "confidence_score": _get("confidence_score", 1.0),
            "knowledge_version": _get("knowledge_version", "v1.0"),
        })
    return records


# ── Knowledge version helpers ──────────────────────────────────────────────────

def latest_version(db_path: Path) -> str:
    if not db_path.exists():
        return "v1.0"
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT version FROM knowledge_versions ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return row["version"] if row else "v1.0"


def next_patch_version(current: str) -> str:
    try:
        prefix, rest = current.lstrip("v"), ""
        parts = prefix.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return "v" + ".".join(parts)
    except (ValueError, IndexError):
        return "v1.1"


def record_version(
    connection: sqlite3.Connection, version: str, record_count: int, note: str = ""
) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO knowledge_versions (version, record_count, note) VALUES (?,?,?)",
        (version, record_count, note),
    )


# ── Seed helpers ───────────────────────────────────────────────────────────────

def load_seed_problems(seed_path: Path | None = None) -> list[KnowledgeProblem]:
    path = seed_path or settings.seed_data_path
    seed_items = json.loads(path.read_text(encoding="utf-8"))
    return [KnowledgeProblem.model_validate(item) for item in seed_items]


def seed_database(
    db_path: Path | None = None,
    seed_path: Path | None = None,
    reset: bool = True,
) -> int:
    path = db_path or settings.database_path
    if reset:
        reset_database(path)
    else:
        initialize_schema(path)

    problems = load_seed_problems(seed_path)
    with get_connection(path) as connection:
        if not reset:
            existing = int(
                connection.execute("SELECT COUNT(*) AS total FROM problems").fetchone()["total"]
            )
            if existing > 0:
                return existing

        for problem in problems:
            problem_id = insert_problem(connection, problem)
            connection.execute(
                "INSERT INTO problem_search(rowid, problem, category, search_text) VALUES (?,?,?,?)",
                (problem_id, problem.problem, problem.category, problem.search_text()),
            )

        total = int(
            connection.execute("SELECT COUNT(*) AS total FROM problems").fetchone()["total"]
        )
        record_version(connection, "v1.0", total, "Initial seed data.")
    return total


# ── Analytics helpers ──────────────────────────────────────────────────────────

def insert_analytics_event(
    db_path: Path,
    event_type: str,
    category: str = "",
    problem: str = "",
    confidence: float = 0.0,
    language: str = "en",
    user_id: int | None = None,
    organization_id: int | None = None,
    knowledge_version: str = "",
    session_id: str = "",
) -> None:
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO analytics_events
                (event_type, category, problem, confidence, language,
                 user_id, organization_id, knowledge_version, session_id)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (event_type, category, problem, confidence, language,
             user_id, organization_id, knowledge_version, session_id),
        )


def fetch_analytics_summary(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {}
    with get_connection(db_path) as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM analytics_events").fetchone()[0])
        by_cat = conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM analytics_events WHERE category!='' "
            "GROUP BY category ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        avg_conf = conn.execute(
            "SELECT AVG(confidence) FROM analytics_events WHERE confidence > 0"
        ).fetchone()[0]
        by_type = conn.execute(
            "SELECT event_type, COUNT(*) AS cnt FROM analytics_events "
            "GROUP BY event_type ORDER BY cnt DESC"
        ).fetchall()
    return {
        "total_events": total,
        "average_confidence": round(float(avg_conf or 0), 2),
        "top_categories": [{"category": r["category"], "count": r["cnt"]} for r in by_cat],
        "events_by_type": [{"event_type": r["event_type"], "count": r["cnt"]} for r in by_type],
    }


# ── Report helpers ─────────────────────────────────────────────────────────────

def insert_report(
    db_path: Path,
    report_type: str,
    title: str,
    content: dict,
    fmt: str = "json",
    file_path: str = "",
    user_id: int | None = None,
    organization_id: int | None = None,
) -> int:
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO reports (report_type, title, content, format, file_path,
                                 user_id, organization_id)
            VALUES (?,?,?,?,?,?,?)
            """,
            (report_type, title, json.dumps(content, ensure_ascii=False),
             fmt, file_path, user_id, organization_id),
        )
        return int(cursor.lastrowid)


def fetch_reports(
    db_path: Path,
    report_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with get_connection(db_path) as conn:
        if report_type:
            rows = conn.execute(
                "SELECT * FROM reports WHERE report_type=? ORDER BY created_at DESC LIMIT ?",
                (report_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [
        {
            "id": r["id"], "report_type": r["report_type"], "title": r["title"],
            "content": json.loads(r["content"]), "format": r["format"],
            "file_path": r["file_path"], "created_at": r["created_at"],
        }
        for r in rows
    ]
