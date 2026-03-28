"""
LottoMirato - Database SQLite
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lottomirato.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ruota TEXT NOT NULL,
            ambo_1 INTEGER NOT NULL,
            ambo_2 INTEGER NOT NULL,
            estratto INTEGER NOT NULL,
            attiva INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS user_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            budget_per_estrazione REAL DEFAULT 6,
            estrazioni_pianificate INTEGER DEFAULT 10,
            data_inizio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS extractions_played (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            data_estrazione TEXT NOT NULL,
            giocata INTEGER DEFAULT 0,
            speso REAL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, data_estrazione)
        );
    """)
    conn.commit()
    conn.close()


def create_user(username, password_hash, display_name=None):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username.lower().strip(), password_hash, display_name or username)
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username.lower().strip(),)).fetchone()
        return dict(user)
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username.lower().strip(),)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


# --- Strategies ---

def save_strategies(user_id, strategies):
    """Sostituisce tutte le strategie di un utente."""
    conn = get_db()
    conn.execute("DELETE FROM strategies WHERE user_id = ?", (user_id,))
    for s in strategies:
        conn.execute(
            "INSERT INTO strategies (user_id, ruota, ambo_1, ambo_2, estratto, attiva) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, s["ruota"], s["ambo"][0], s["ambo"][1], s["estratto"], 1)
        )
    conn.commit()
    conn.close()


def get_strategies(user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM strategies WHERE user_id = ? AND attiva = 1", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Plans ---

def save_plan(user_id, budget_per_estr=6, estrazioni=10, data_inizio=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO user_plans (user_id, budget_per_estrazione, estrazioni_pianificate, data_inizio)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            budget_per_estrazione = excluded.budget_per_estrazione,
            estrazioni_pianificate = excluded.estrazioni_pianificate,
            data_inizio = excluded.data_inizio
    """, (user_id, budget_per_estr, estrazioni, data_inizio))
    conn.commit()
    conn.close()


def get_plan(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM user_plans WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else {"budget_per_estrazione": 6, "estrazioni_pianificate": 10}


# --- Extractions Played ---

def toggle_extraction(user_id, data, giocata, budget_per_estr=6):
    conn = get_db()
    speso = budget_per_estr if giocata else 0
    conn.execute("""
        INSERT INTO extractions_played (user_id, data_estrazione, giocata, speso)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, data_estrazione) DO UPDATE SET
            giocata = excluded.giocata,
            speso = excluded.speso
    """, (user_id, data, 1 if giocata else 0, speso))
    conn.commit()
    conn.close()


def get_extractions_played(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM extractions_played WHERE user_id = ? ORDER BY data_estrazione",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_budget_spent(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(speso), 0) as total FROM extractions_played WHERE user_id = ? AND giocata = 1",
        (user_id,)
    ).fetchone()
    conn.close()
    return row["total"] if row else 0


def seed_default_user(password_hash):
    """Crea l'utente danitech con la strategia pre-configurata."""
    user = get_user_by_username("danitech")
    if user:
        return user

    user = create_user("danitech", password_hash, "Dani")
    if not user:
        return None

    uid = user["id"]

    # Strategia: 41-11 Bari, 45-85 Milano, 47-90 Firenze
    save_strategies(uid, [
        {"ruota": "BA", "ambo": [41, 11], "estratto": 41},
        {"ruota": "MI", "ambo": [45, 85], "estratto": 45},
        {"ruota": "FI", "ambo": [47, 90], "estratto": 47},
    ])

    # Piano: 10 estrazioni, 6€ ciascuna
    save_plan(uid, 6, 10, "2026/03/27")

    # Estrazione 1 giocata
    toggle_extraction(uid, "2026/03/27", True, 6)

    return user
