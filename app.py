import os
import hashlib
import sqlite3
import json
from functools import wraps
from flask import Flask, request, jsonify, render_template, make_response

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

PASSPHRASE = os.environ.get("PASSPHRASE", "changeme")
DB_PATH = "/data/tasks.db" if os.path.isdir("/data") else os.path.join(os.path.dirname(__file__), "tasks.db")


def hash_passphrase(p):
    return hashlib.sha256(p.encode()).hexdigest()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignee TEXT NOT NULL CHECK(assignee IN ('adam', 'catherine', 'lindsey')),
            title TEXT NOT NULL,
            notes TEXT DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'med' CHECK(priority IN ('high', 'med', 'low')),
            status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done')),
            due_date TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TRIGGER IF NOT EXISTS update_timestamp
        AFTER UPDATE ON tasks
        FOR EACH ROW
        BEGIN
            UPDATE tasks SET updated_at = datetime('now') WHERE id = OLD.id;
        END;
    """)
    # Migrate: rebuild table if CHECK constraint doesn't include 'lindsey'
    try:
        conn.execute("INSERT INTO tasks (assignee, title) VALUES ('lindsey', '_migration_test')")
        conn.execute("DELETE FROM tasks WHERE title = '_migration_test'")
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.executescript("""
            CREATE TABLE tasks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignee TEXT NOT NULL CHECK(assignee IN ('adam', 'catherine', 'lindsey')),
                title TEXT NOT NULL,
                notes TEXT DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'med' CHECK(priority IN ('high', 'med', 'low')),
                status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done')),
                due_date TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO tasks_new SELECT * FROM tasks;
            DROP TABLE tasks;
            ALTER TABLE tasks_new RENAME TO tasks;
            CREATE TRIGGER IF NOT EXISTS update_timestamp
            AFTER UPDATE ON tasks
            FOR EACH ROW
            BEGIN
                UPDATE tasks SET updated_at = datetime('now') WHERE id = OLD.id;
            END;
        """)
    conn.commit()
    conn.close()


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_cookie = request.cookies.get("auth")
        if auth_cookie != hash_passphrase(PASSPHRASE):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def row_to_dict(row):
    return dict(row)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/auth", methods=["POST"])
def auth():
    data = request.get_json()
    if not data or data.get("passphrase") != PASSPHRASE:
        return jsonify({"error": "Wrong passphrase"}), 403
    resp = make_response(jsonify({"ok": True}))
    resp.set_cookie("auth", hash_passphrase(PASSPHRASE), max_age=30 * 24 * 3600, httponly=True, samesite="Lax")
    return resp


@app.route("/api/tasks", methods=["GET"])
@require_auth
def get_tasks():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks ORDER BY assignee, sort_order").fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("assignee"):
        return jsonify({"error": "title and assignee required"}), 400
    if data["assignee"] not in ("adam", "catherine", "lindsey"):
        return jsonify({"error": "assignee must be adam or catherine"}), 400

    conn = get_db()
    # Set sort_order to max + 1 for this assignee
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM tasks WHERE assignee = ?",
        (data["assignee"],)
    ).fetchone()[0]

    cursor = conn.execute(
        """INSERT INTO tasks (assignee, title, notes, priority, status, due_date, sort_order)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["assignee"],
            data["title"],
            data.get("notes", ""),
            data.get("priority", "med"),
            data.get("status", "todo"),
            data.get("due_date"),
            max_order + 1,
        )
    )
    task_id = cursor.lastrowid
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.commit()
    conn.close()
    return jsonify(row_to_dict(task)), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = {"assignee", "title", "notes", "priority", "status", "due_date", "sort_order"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({"error": "No valid fields"}), 400

    conn = get_db()
    existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
    conn.commit()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return jsonify(row_to_dict(task))


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task(task_id):
    conn = get_db()
    existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/reorder", methods=["PUT"])
@require_auth
def reorder_task(task_id):
    data = request.get_json()
    new_order = data.get("new_order")
    if new_order is None:
        return jsonify({"error": "new_order required"}), 400

    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    assignee = task["assignee"]
    tasks = conn.execute(
        "SELECT id FROM tasks WHERE assignee = ? ORDER BY sort_order",
        (assignee,)
    ).fetchall()

    task_ids = [r["id"] for r in tasks]
    if task_id in task_ids:
        task_ids.remove(task_id)
    new_order = max(0, min(new_order, len(task_ids)))
    task_ids.insert(new_order, task_id)

    for i, tid in enumerate(task_ids):
        conn.execute("UPDATE tasks SET sort_order = ? WHERE id = ?", (i, tid))

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
