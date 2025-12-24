# (replace your existing main.py with this - it includes browser auto-open to localhost:8000)
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
import os
import sqlite3
from contextlib import asynccontextmanager
import logging
import sys
import threading
import time
import urllib.request
import webbrowser

# Basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Config (use env vars in production)
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
# Allow frontend dev origins; add your front-end host when deploying
API_ORIGINS = os.environ.get("API_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")

# Use pbkdf2_sha256 to avoid native bcrypt dependency issues on some systems.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

DB_FILE = os.path.join(os.getcwd(), "database.sqlite")

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create users table (idempotent)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE,
      password_hash TEXT,
      display_name TEXT
    )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized (file=%s)", DB_FILE)

def create_default_user():
    """Create a default admin user if missing (username: admin / password: admin)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if cur.fetchone() is None:
        pw = pwd_context.hash("admin")
        cur.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            ("admin", pw, "Administrator")
        )
        conn.commit()
        logger.info("Default user 'admin' created (pwd: admin) - change this in production.")
    conn.close()

# Lifespan handler (startup & shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Lifespan startup: initializing database and default data...")
        init_db()
        create_default_user()
        logger.info("Startup actions complete.")
        yield
    except Exception as e:
        logger.exception("Exception during startup: %s", e)
        raise
    finally:
        logger.info("Lifespan shutdown (if any cleanup needed).")

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in API_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Auth & helper functions
# -------------------------
class LoginPayload(BaseModel):
    username: str
    password: str

def create_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_user_by_username(username: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None

def get_current_user_from_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            return None
        user = get_user_by_username(username)
        return user
    except JWTError:
        return None

# -------------------------
# API endpoints
# -------------------------
@app.post("/api/login")
def login(payload: LoginPayload, response: Response):
    user = get_user_by_username(payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_token({"sub": user["username"], "type": "access"},
                                expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token({"sub": user["username"], "type": "refresh"},
                                 expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    secure_flag = True if os.environ.get("ENV") == "production" else False
    response.set_cookie("access_token", access_token, httponly=True, secure=secure_flag, samesite="lax",
                        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=secure_flag, samesite="lax",
                        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)
    logger.info("User '%s' logged in", user["username"])
    return {"ok": True, "username": user["username"], "display_name": user.get("display_name")}

@app.get("/api/me")
def me(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_current_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": user["username"], "display_name": user.get("display_name")}

@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"ok": True}

@app.post("/api/refresh")
def refresh(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(rt, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Bad token type")
    username = payload.get("sub")
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access_token = create_token({"sub": user["username"], "type": "access"},
                                expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    secure_flag = True if os.environ.get("ENV") == "production" else False
    response.set_cookie("access_token", access_token, httponly=True, secure=secure_flag, samesite="lax",
                        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    return {"ok": True}

# -------------------------
# Serve React build (if exists)
# -------------------------
if os.path.isdir("build"):
    logger.info("Mounting 'build' directory to serve React static files.")
    app.mount("/", StaticFiles(directory="build", html=True), name="static")
else:
    logger.info("No 'build' directory found. Build frontend with 'npm run build' and place it in project root as 'build/'.")

# -------------------------
# Helper: open browser when server ready
# -------------------------
def open_browser_when_ready(url="http://127.0.0.1:8000", timeout=10):
    def _open():
        logger.info("Waiting for %s to be ready (timeout %ss)...", url, timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        logger.info("%s is ready, opening browser.", url)
                        webbrowser.open(url)
                        return
            except Exception:
                time.sleep(0.2)
        logger.info("Timed out waiting for %s; opening browser anyway.", url)
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()

# -------------------------
# Run guard: allow `python main.py`
# -------------------------
if __name__ == "__main__":
    logger.info("Starting uvicorn server from __main__ (host=127.0.0.1 port=8000, reload=True).")
    # Start a background thread that opens the browser when the server responds.
    open_browser_when_ready("http://127.0.0.1:8000", timeout=8)
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
