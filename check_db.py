import sqlite3
import json
from pathlib import Path

def get_cookies():
    db_path = "D:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/.vidgen/nav.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT cookie_path FROM accounts LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row: return row[0]
    return None

cookie_dir = get_cookies()
print(f"Cookies at: {cookie_dir}")
