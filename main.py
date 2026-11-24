"""
Scar Client - HWID Authentication API
Deploy on Railway.app (free tier)
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os
import hashlib
from datetime import datetime

app = FastAPI(title="Scar Client API", version="1.0.0")

DB_PATH = os.environ.get("DB_PATH", "scar.db")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "changeme_scar_secret_2024")

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hwid        TEXT NOT NULL UNIQUE,
            discord_id  TEXT,
            username    TEXT,
            whitelisted INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL,
            expires_at  TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------------------------
# Auth middleware (admin token check)
# ---------------------------------------------------------------------------
def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class CheckRequest(BaseModel):
    hwid: str

class AddUserRequest(BaseModel):
    hwid: str
    discord_id: Optional[str] = None
    username: Optional[str] = None
    expires_at: Optional[str] = None  # ISO format: "2025-12-31T23:59:59"

class UpdateUserRequest(BaseModel):
    whitelisted: Optional[bool] = None
    username: Optional[str] = None
    expires_at: Optional[str] = None

# ---------------------------------------------------------------------------
# Public endpoint: check HWID (called by injector)
# ---------------------------------------------------------------------------
@app.post("/check")
def check_hwid(req: CheckRequest):
    """
    Called by Scar.exe before injecting.
    Returns {"allowed": true/false, "reason": "..."}
    """
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE hwid = ?", (req.hwid,)
    ).fetchone()
    conn.close()

    if row is None:
        return {"allowed": False, "reason": "HWID not registered. Contact support on Discord."}

    if not row["whitelisted"]:
        return {"allowed": False, "reason": "Your access has been revoked. Contact support on Discord."}

    if row["expires_at"]:
        try:
            exp = datetime.fromisoformat(row["expires_at"])
            if datetime.utcnow() > exp:
                return {"allowed": False, "reason": "Your license has expired. Renew on Discord."}
        except Exception:
            pass

    return {"allowed": True, "reason": "Welcome, " + (row["username"] or "user") + "!"}

# ---------------------------------------------------------------------------
# Admin endpoints (protected by ADMIN_SECRET header)
# ---------------------------------------------------------------------------
@app.get("/admin/users", dependencies=[Depends(require_admin)])
def list_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/admin/users", dependencies=[Depends(require_admin)])
def add_user(req: AddUserRequest):
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO users (hwid, discord_id, username, whitelisted, created_at, expires_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (req.hwid, req.discord_id, req.username,
             datetime.utcnow().isoformat(), req.expires_at)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="HWID already exists")
    conn.close()
    return {"success": True, "message": "User added"}

@app.patch("/admin/users/{hwid}", dependencies=[Depends(require_admin)])
def update_user(hwid: str, req: UpdateUserRequest):
    conn = get_db()
    updates = {}
    if req.whitelisted is not None:
        updates["whitelisted"] = 1 if req.whitelisted else 0
    if req.username is not None:
        updates["username"] = req.username
    if req.expires_at is not None:
        updates["expires_at"] = req.expires_at

    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="Nothing to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [hwid]
    conn.execute(f"UPDATE users SET {set_clause} WHERE hwid = ?", values)
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/admin/users/{hwid}", dependencies=[Depends(require_admin)])
def delete_user(hwid: str):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE hwid = ?", (hwid,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/health")
def health():
    return {"status": "ok", "service": "Scar Client API"}
