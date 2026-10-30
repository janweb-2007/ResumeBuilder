
import sqlite3
import hashlib

DB_NAME = "resume_builder.db"

FIELDS = ["name", "phone", "email", "summary", "education", "skills",
          "experience", "projects", "photo_path", "template", "color", "job_description"]


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT, phone TEXT, email TEXT, summary TEXT,
            education TEXT, skills TEXT, experience TEXT, projects TEXT,
            photo_path TEXT, template TEXT, color TEXT, job_description TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def sign_up(username, password):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def login(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row and row["password_hash"] == hash_password(password):
        return row["id"]
    return None


def save_resume(user_id, data):
    conn = get_connection()
    cur = conn.cursor()
    columns = ", ".join(FIELDS)
    placeholders = ", ".join(["?"] * (len(FIELDS) + 1))
    values = [user_id] + [data.get(f, "") for f in FIELDS]
    cur.execute(f"INSERT INTO resumes (user_id, {columns}) VALUES ({placeholders})", values)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_my_resumes(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM resumes WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_resume(resume_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_resume(resume_id, user_id, data):
    conn = get_connection()
    cur = conn.cursor()
    assignments = ", ".join(f"{f} = ?" for f in FIELDS)
    values = [data.get(f, "") for f in FIELDS] + [resume_id, user_id]
    cur.execute(f"UPDATE resumes SET {assignments} WHERE id = ? AND user_id = ?", values)
    conn.commit()
    conn.close()


def delete_resume(resume_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id))
    conn.commit()
    conn.close()