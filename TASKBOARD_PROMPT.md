# Portfolio Acquisition Task Board — Build Spec

## What This Is

A lightweight shared task board for two people (Adam and Catherine) working together on patent portfolio acquisition. It should be a simple Flask + SQLite web app deployed to Render's free tier. No frameworks, no complexity — just something that works.

## Stack

- **Backend:** Python 3.10+, Flask, SQLite
- **Frontend:** Single-page HTML/CSS/JS (no React, no build step)
- **Deployment:** Render free tier (include a `render.yaml` for one-click deploy)
- **File structure:** Keep it minimal:
  ```
  app.py              # Everything backend
  templates/index.html # Everything frontend (inline CSS + JS)
  requirements.txt
  render.yaml
  README.md
  ```

## Authentication

Dead simple passphrase gate. No user accounts, no sessions table.

- Store a `PASSPHRASE` in an environment variable (default to `"changeme"` for local dev)
- On first visit, show a simple passphrase input screen
- On correct entry, set a cookie (`auth=<hashed_passphrase>`) that lasts 30 days
- Every API request checks the cookie — return 401 if missing/wrong
- That's it. No user management, no registration, no password reset

## Database Schema

One SQLite table. Keep it flat.

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignee TEXT NOT NULL CHECK(assignee IN ('adam', 'catherine')),
    title TEXT NOT NULL,
    notes TEXT DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'med' CHECK(priority IN ('high', 'med', 'low')),
    status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done')),
    due_date TEXT,  -- ISO format YYYY-MM-DD or NULL
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Add a trigger to auto-update `updated_at` on any row change.

## API Endpoints

All return JSON. All require the auth cookie.

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/api/tasks` | Return all tasks ordered by assignee, then sort_order |
| POST | `/api/tasks` | Create a task. Body: `{assignee, title, notes?, priority?, status?, due_date?}` |
| PUT | `/api/tasks/<id>` | Update any fields on a task. Body: partial update object |
| DELETE | `/api/tasks/<id>` | Delete a task |
| PUT | `/api/tasks/<id>/reorder` | Move a task. Body: `{new_order: int}`. Recompute sort_order for all tasks of that assignee |
| POST | `/api/auth` | Check passphrase, set cookie. Body: `{passphrase: string}` |

## Frontend Layout

Two-column layout. Catherine on the left, Adam on the right. Each column has its own "+ Add Task" button at the top.

### Task Card

Each card shows:
- **Checkbox** on the left to toggle done (moves to "Done" section at bottom)
- **Title** (bold)
- **Priority badge** — High (red), Med (amber), Low (gray)
- **Status indicator** — To Do, In Progress, Done
- **Due date** if set, with red highlight if overdue
- **Notes preview** — first ~80 chars, expandable
- **Action buttons** — Edit (pencil icon), Move Up/Down arrows, Delete (trash icon)

### Task Ordering

- Within each person's column, tasks are ordered by `sort_order`
- Up/Down arrow buttons swap a task with its neighbor
- Drag-and-drop is nice-to-have but NOT required — arrow buttons are fine

### Task Grouping Within Each Column

Group tasks by status in this order:
1. **In Progress** (highlighted, top of column)
2. **To Do** (main body)
3. **Done** (collapsed by default, toggle to show)

### Add/Edit Task Modal

Simple modal form with:
- Title (text input, required)
- Assignee (pre-filled based on which column's "+" was clicked, but changeable)
- Notes (textarea)
- Priority (three toggle buttons: High / Med / Low)
- Status (three toggle buttons: To Do / In Progress / Done)
- Due Date (date picker, optional)
- Save / Cancel / Delete (delete only in edit mode)

### Polling

- Frontend polls `GET /api/tasks` every 5 seconds
- On receiving new data, re-render only if the data has changed (compare a hash or timestamp)
- Show a small "Last synced: 12:34:05 PM" indicator in the header

### Style

- Clean, professional, not flashy
- White background, subtle borders, good spacing
- Catherine's column header: purple accent (#8b5cf6)
- Adam's column header: blue accent (#3b82f6)
- Mobile responsive — stack columns vertically on narrow screens
- Use system fonts (`system-ui, -apple-system, sans-serif`)

## Deployment Config

### render.yaml

```yaml
services:
  - type: web
    name: portfolio-taskboard
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: PASSPHRASE
        sync: false
      - key: FLASK_SECRET_KEY
        generateValue: true
    disk:
      name: data
      mountPath: /data
      sizeGB: 1
```

### Important Render Notes

- SQLite file must live on the persistent disk (`/data/tasks.db`), not in the repo directory (which gets wiped on redeploy)
- Use `gunicorn` as the production server — add it to `requirements.txt`
- The free tier spins down after 15 min of inactivity; first request after that takes ~30 seconds. This is fine.

### requirements.txt

```
flask
gunicorn
```

That's it. No other dependencies needed — SQLite is built into Python.

## Local Development

The app should work locally with:

```bash
pip install flask
python app.py
```

- In local dev mode, store the DB in the project directory (`./tasks.db`)
- In production (when `/data` exists), store it at `/data/tasks.db`
- Default passphrase for local dev: `changeme`
- Run on port 5000 locally

## README.md

Include a short README with:
1. What this is (one sentence)
2. Local setup (3 steps: clone, pip install, python app.py)
3. Deploy to Render (connect GitHub repo, set PASSPHRASE env var, deploy)
4. That's it

## What NOT to Build

- No user accounts or registration
- No WebSockets (polling is fine for two people)
- No JavaScript framework (vanilla JS only)
- No CSS framework (write the CSS inline or in a style tag)
- No task comments/threads
- No file attachments
- No email notifications
- No activity log
- No dark mode (unless it's trivial)
