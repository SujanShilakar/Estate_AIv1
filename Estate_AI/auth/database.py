"""
SQLite database layer for Estate AI.
Handles users, sessions, generation history, templates, compliance rules.
"""
import sqlite3
import os
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "estate_ai.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    """Context manager for DB connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_password(password: str, salt: str = None) -> tuple:
    """Hash password with SHA-256 + salt. Returns (hash, salt)."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return h, salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against stored hash."""
    h, _ = hash_password(password, salt)
    return h == stored_hash


def init_db():
    """Initialise schema and seed default admin + demo agent."""
    with get_db() as conn:
        c = conn.cursor()

        # Users table — agents and admins
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT UNIQUE NOT NULL,
                email        TEXT UNIQUE NOT NULL,
                password     TEXT NOT NULL,
                salt         TEXT NOT NULL,
                role         TEXT NOT NULL DEFAULT 'agent',
                full_name    TEXT,
                agency       TEXT,
                phone        TEXT,
                is_active    INTEGER DEFAULT 1,
                created_at   TEXT NOT NULL,
                last_login   TEXT
            )
        """)

        # Sessions table
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                created_at  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Generation history
        c.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                created_at      TEXT NOT NULL,
                suburb          TEXT,
                beds            TEXT,
                baths           TEXT,
                parking         TEXT,
                price           TEXT,
                tone            TEXT,
                prop_type       TEXT,
                listing         TEXT,
                ads             TEXT,
                room_desc       TEXT,
                floor_plan_desc TEXT,
                analysis        TEXT,
                images          TEXT,
                language        TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Listing templates (admin-managed)
        c.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                tone        TEXT NOT NULL,
                content     TEXT NOT NULL,
                description TEXT,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)

        # Compliance rules (admin-managed)
        c.execute("""
            CREATE TABLE IF NOT EXISTS compliance_rules (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name   TEXT NOT NULL,
                pattern     TEXT NOT NULL,
                severity    TEXT NOT NULL DEFAULT 'warning',
                message     TEXT NOT NULL,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT NOT NULL
            )
        """)

        # Seed default admin
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if c.fetchone()[0] == 0:
            pwd, salt = hash_password("admin123")
            c.execute("""
                INSERT INTO users (username, email, password, salt, role, full_name, agency, created_at)
                VALUES (?, ?, ?, ?, 'admin', ?, ?, ?)
            """, ("admin", "admin@estateai.com", pwd, salt, "System Administrator", "Estate AI", datetime.utcnow().isoformat()))

        # Seed demo agent
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'agent'")
        if c.fetchone()[0] == 0:
            pwd, salt = hash_password("agent123")
            c.execute("""
                INSERT INTO users (username, email, password, salt, role, full_name, agency, phone, created_at)
                VALUES (?, ?, ?, ?, 'agent', ?, ?, ?, ?)
            """, ("agent", "agent@estateai.com", pwd, salt, "Demo Agent", "Adelaide Realty", "+61 400 000 000", datetime.utcnow().isoformat()))

        # Seed default compliance rules (Australian real estate guidelines)
        c.execute("SELECT COUNT(*) FROM compliance_rules")
        if c.fetchone()[0] == 0:
            default_rules = [
                ("No price baiting", r"\b(starting from|from only|as low as)\b", "warning",
                 "Avoid 'starting from' / 'from only' phrasing — may breach underquoting laws."),
                ("No guaranteed returns", r"\b(guaranteed return|guaranteed profit|guaranteed rental)\b", "error",
                 "Investment guarantees are prohibited under ASIC and state Fair Trading laws."),
                ("Avoid superlatives without proof", r"\b(best|biggest|cheapest|number one)\b", "warning",
                 "Unsubstantiated superlatives may breach Australian Consumer Law."),
                ("No discriminatory language", r"\b(no kids|no children|no pets allowed|adults only)\b", "error",
                 "Discriminatory rental phrasing may breach anti-discrimination law."),
                ("Avoid absolute claims", r"\b(perfect|flawless|immaculate condition)\b", "warning",
                 "Absolute claims require substantiation under ACL."),
            ]
            for name, pattern, severity, msg in default_rules:
                c.execute("""
                    INSERT INTO compliance_rules (rule_name, pattern, severity, message, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, pattern, severity, msg, datetime.utcnow().isoformat()))

        # Seed default templates
        c.execute("SELECT COUNT(*) FROM templates")
        if c.fetchone()[0] == 0:
            default_templates = [
                ("Professional Standard", "professional",
                 "Presenting this {beds} bedroom, {baths} bathroom {prop_type} in the desirable suburb of {suburb}.",
                 "Default professional opener for general listings"),
                ("Luxury Premium", "luxury",
                 "Welcome to an extraordinary residence in the prestigious suburb of {suburb}.",
                 "Premium tone for high-end properties"),
                ("Family Focused", "family",
                 "Welcome home to this wonderful family residence in the heart of {suburb}!",
                 "Warm, family-oriented opener"),
                ("Investment Pitch", "investment",
                 "Outstanding investment opportunity now available in {suburb}!",
                 "Investor-focused with rental appeal emphasis"),
            ]
            now = datetime.utcnow().isoformat()
            for name, tone, content, desc in default_templates:
                c.execute("""
                    INSERT INTO templates (name, tone, content, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, tone, content, desc, now, now))


# ── User helpers ─────────────────────────────────
def create_user(username, email, password, role="agent", full_name="", agency="", phone=""):
    pwd, salt = hash_password(password)
    with get_db() as conn:
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO users (username, email, password, salt, role, full_name, agency, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, email, pwd, salt, role, full_name, agency, phone, datetime.utcnow().isoformat()))
            return c.lastrowid
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Username or email already exists") from e


def get_user_by_username(username):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
        row = c.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None


def list_users(role=None):
    with get_db() as conn:
        c = conn.cursor()
        if role:
            c.execute("SELECT id, username, email, role, full_name, agency, phone, is_active, created_at, last_login FROM users WHERE role = ? ORDER BY created_at DESC", (role,))
        else:
            c.execute("SELECT id, username, email, role, full_name, agency, phone, is_active, created_at, last_login FROM users ORDER BY created_at DESC")
        return [dict(r) for r in c.fetchall()]


def update_user_active(user_id, is_active):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))


def delete_user(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id = ? AND role != 'admin'", (user_id,))


def update_last_login(user_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.utcnow().isoformat(), user_id))


# ── Session helpers ─────────────────────────────
def create_session(user_id, days=7):
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    expires = now + timedelta(days=days)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                  (token, user_id, now.isoformat(), expires.isoformat()))
    return token


def get_session_user(token):
    if not token:
        return None
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.* FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
        """, (token, datetime.utcnow().isoformat()))
        row = c.fetchone()
        return dict(row) if row else None


def delete_session(token):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ── Generation history helpers ──────────────────
def save_generation(user_id, data):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO generations
            (user_id, created_at, suburb, beds, baths, parking, price, tone, prop_type,
             listing, ads, room_desc, floor_plan_desc, analysis, images, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            datetime.utcnow().isoformat(),
            data.get("suburb"), data.get("beds"), data.get("baths"),
            data.get("parking"), data.get("price"), data.get("tone"),
            data.get("prop_type"),
            data.get("listing"), json.dumps(data.get("ads", [])),
            data.get("room_desc"), data.get("floor_plan_desc"),
            json.dumps(data.get("analysis", {})),
            json.dumps(data.get("images", [])),
            data.get("language", "en"),
        ))
        return c.lastrowid


def list_generations(user_id=None, limit=100):
    with get_db() as conn:
        c = conn.cursor()
        if user_id:
            c.execute("""
                SELECT g.*, u.username, u.full_name FROM generations g
                JOIN users u ON g.user_id = u.id
                WHERE g.user_id = ?
                ORDER BY g.created_at DESC LIMIT ?
            """, (user_id, limit))
        else:
            c.execute("""
                SELECT g.*, u.username, u.full_name FROM generations g
                JOIN users u ON g.user_id = u.id
                ORDER BY g.created_at DESC LIMIT ?
            """, (limit,))
        return [dict(r) for r in c.fetchall()]


def get_generation(gen_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT g.*, u.username, u.full_name FROM generations g
            JOIN users u ON g.user_id = u.id
            WHERE g.id = ?
        """, (gen_id,))
        row = c.fetchone()
        return dict(row) if row else None


def delete_generation(gen_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM generations WHERE id = ?", (gen_id,))


# ── Templates ───────────────────────────────────
def list_templates(active_only=False):
    with get_db() as conn:
        c = conn.cursor()
        if active_only:
            c.execute("SELECT * FROM templates WHERE is_active = 1 ORDER BY tone, name")
        else:
            c.execute("SELECT * FROM templates ORDER BY tone, name")
        return [dict(r) for r in c.fetchall()]


def create_template(name, tone, content, description):
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO templates (name, tone, content, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, tone, content, description, now, now))
        return c.lastrowid


def update_template(tid, name, tone, content, description, is_active):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE templates SET name = ?, tone = ?, content = ?, description = ?,
                                 is_active = ?, updated_at = ?
            WHERE id = ?
        """, (name, tone, content, description, 1 if is_active else 0,
              datetime.utcnow().isoformat(), tid))


def delete_template(tid):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM templates WHERE id = ?", (tid,))


# ── Compliance rules ────────────────────────────
def list_compliance_rules(active_only=False):
    with get_db() as conn:
        c = conn.cursor()
        if active_only:
            c.execute("SELECT * FROM compliance_rules WHERE is_active = 1 ORDER BY severity DESC, rule_name")
        else:
            c.execute("SELECT * FROM compliance_rules ORDER BY severity DESC, rule_name")
        return [dict(r) for r in c.fetchall()]


def create_compliance_rule(rule_name, pattern, severity, message):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO compliance_rules (rule_name, pattern, severity, message, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (rule_name, pattern, severity, message, datetime.utcnow().isoformat()))
        return c.lastrowid


def update_compliance_rule(rid, rule_name, pattern, severity, message, is_active):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE compliance_rules SET rule_name = ?, pattern = ?, severity = ?,
                                        message = ?, is_active = ?
            WHERE id = ?
        """, (rule_name, pattern, severity, message, 1 if is_active else 0, rid))


def delete_compliance_rule(rid):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM compliance_rules WHERE id = ?", (rid,))


def check_compliance(text):
    """Return list of compliance violations found in text."""
    import re
    rules = list_compliance_rules(active_only=True)
    violations = []
    for rule in rules:
        try:
            if re.search(rule["pattern"], text, re.IGNORECASE):
                violations.append({
                    "rule_name": rule["rule_name"],
                    "severity":  rule["severity"],
                    "message":   rule["message"],
                })
        except re.error:
            continue
    return violations


# ── Analytics ───────────────────────────────────
def get_analytics():
    with get_db() as conn:
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM users WHERE role = 'agent'")
        total_agents = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE role = 'agent' AND is_active = 1")
        active_agents = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations")
        total_generations = c.fetchone()[0]

        # Generations in last 7 days
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        c.execute("SELECT COUNT(*) FROM generations WHERE created_at > ?", (cutoff,))
        gens_7d = c.fetchone()[0]

        # Generations per day (last 14 days)
        c.execute("""
            SELECT DATE(created_at) AS day, COUNT(*) AS cnt FROM generations
            WHERE created_at > ?
            GROUP BY DATE(created_at) ORDER BY day
        """, ((datetime.utcnow() - timedelta(days=14)).isoformat(),))
        per_day = [dict(r) for r in c.fetchall()]

        # Top agents by generation count
        c.execute("""
            SELECT u.username, u.full_name, COUNT(g.id) AS cnt
            FROM users u LEFT JOIN generations g ON u.id = g.user_id
            WHERE u.role = 'agent'
            GROUP BY u.id ORDER BY cnt DESC LIMIT 5
        """)
        top_agents = [dict(r) for r in c.fetchall()]

        # Tone distribution
        c.execute("SELECT tone, COUNT(*) AS cnt FROM generations GROUP BY tone")
        tone_dist = [dict(r) for r in c.fetchall()]

        # Top suburbs
        c.execute("""
            SELECT suburb, COUNT(*) AS cnt FROM generations
            WHERE suburb IS NOT NULL AND suburb != ''
            GROUP BY suburb ORDER BY cnt DESC LIMIT 5
        """)
        top_suburbs = [dict(r) for r in c.fetchall()]

        return {
            "total_agents":      total_agents,
            "active_agents":     active_agents,
            "total_generations": total_generations,
            "generations_7d":    gens_7d,
            "per_day":           per_day,
            "top_agents":        top_agents,
            "tone_distribution": tone_dist,
            "top_suburbs":       top_suburbs,
        }
