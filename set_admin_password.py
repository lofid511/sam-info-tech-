#!/usr/bin/env python3
import sqlite3
import os
import sys
from passlib.context import CryptContext

# Use same hashing scheme as main.py
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

DB_FILE = os.path.join(os.getcwd(), "database.sqlite")

def set_admin_password(new_password):
    if not new_password:
        print("Usage: python set_admin_password.py NEW_PASSWORD")
        return 1
    if not os.path.isfile(DB_FILE):
        print("Database not found:", DB_FILE)
        return 1
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    hashed = pwd_context.hash(new_password)
    cur.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed, "admin"))
    if cur.rowcount == 0:
        # create admin if missing
        cur.execute("INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                    ("admin", hashed, "Administrator"))
        print("Admin user created with provided password.")
    else:
        print("Admin password updated.")
    conn.commit()
    conn.close()
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python set_admin_password.py NEW_PASSWORD")
        sys.exit(1)
    sys.exit(set_admin_password(sys.argv[1]))