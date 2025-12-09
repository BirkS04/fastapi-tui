"""
TUI Persistence Layer

Speichert TUI-Events in einer SQLite-Datenbank für Session-Persistenz.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import uuid

DB_PATH = "tui_events.db"

class TUIPersistence:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.current_session_id = None
        self._init_db()
        self.start_new_session()
    
    def _init_db(self):
        """Initialisiert die Datenbank-Tabellen"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Sessions Table
        c.execute('''CREATE TABLE IF NOT EXISTS sessions
                     (id TEXT PRIMARY KEY, start_time TIMESTAMP, name TEXT)''')
        
        # Endpoint Hits Table (mit session_id)
        c.execute('''CREATE TABLE IF NOT EXISTS endpoint_hits
                     (id TEXT PRIMARY KEY, session_id TEXT, endpoint TEXT, method TEXT, 
                      status_code INTEGER, duration_ms REAL, timestamp TIMESTAMP, 
                      data JSON, FOREIGN KEY(session_id) REFERENCES sessions(id))''')
        
        # Server Logs Table (mit session_id)
        c.execute('''CREATE TABLE IF NOT EXISTS server_logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, level TEXT, 
                      message TEXT, timestamp TIMESTAMP,
                      FOREIGN KEY(session_id) REFERENCES sessions(id))''')
        
        # Migration: Check if session_id exists in old tables (simple check)
        try:
            c.execute("SELECT session_id FROM endpoint_hits LIMIT 1")
        except sqlite3.OperationalError:
            # Column missing, drop tables to reset (Dev Tool -> Data loss acceptable for upgrade)
            print("[PERSISTENCE] Upgrading DB schema (dropping old tables)...")
            c.execute("DROP TABLE IF EXISTS endpoint_hits")
            c.execute("DROP TABLE IF EXISTS server_logs")
            # Re-create
            c.execute('''CREATE TABLE IF NOT EXISTS endpoint_hits
                     (id TEXT PRIMARY KEY, session_id TEXT, endpoint TEXT, method TEXT, 
                      status_code INTEGER, duration_ms REAL, timestamp TIMESTAMP, 
                      data JSON, FOREIGN KEY(session_id) REFERENCES sessions(id))''')
            c.execute('''CREATE TABLE IF NOT EXISTS server_logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, level TEXT, 
                      message TEXT, timestamp TIMESTAMP,
                      FOREIGN KEY(session_id) REFERENCES sessions(id))''')
            
        conn.commit()
        conn.close()

    def start_new_session(self):
        """Startet eine neue Session"""
        self.current_session_id = str(uuid.uuid4())
        start_time = datetime.now()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO sessions (id, start_time, name) VALUES (?, ?, ?)",
                  (self.current_session_id, start_time, f"Session {start_time.strftime('%Y-%m-%d %H:%M')}"))
        conn.commit()
        conn.close()
        return self.current_session_id

    def get_sessions(self) -> List[Dict[str, Any]]:
        """Gibt alle Sessions zurück"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM sessions ORDER BY start_time DESC")
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def delete_session(self, session_id: str):
        """Löscht eine Session und ihre Daten"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM endpoint_hits WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM server_logs WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()

    def save_hit(self, hit_data: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Ensure ID
        if "id" not in hit_data:
            hit_data["id"] = str(uuid.uuid4())
            
        # FIX: INSERT OR REPLACE verwenden!
        # Das verhindert den "UNIQUE constraint failed" Fehler.
        # Wenn die ID schon da ist (Update), wird der Eintrag ersetzt.
        c.execute('''INSERT OR REPLACE INTO endpoint_hits 
                     (id, session_id, endpoint, method, status_code, duration_ms, timestamp, data)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (hit_data["id"], self.current_session_id, hit_data.get("endpoint"), hit_data.get("method"),
                   hit_data.get("status_code"), hit_data.get("duration_ms"), 
                   hit_data.get("timestamp"), json.dumps(hit_data, default=str)))
        conn.commit()
        conn.close()

    def save_log(self, level: str, message: str, timestamp: datetime):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO server_logs (session_id, level, message, timestamp) VALUES (?, ?, ?, ?)",
                  (self.current_session_id, level, message, timestamp))
        conn.commit()
        conn.close()
        
    def get_recent_hits(self, limit: int = 100, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        target_session = session_id or self.current_session_id
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''SELECT data FROM endpoint_hits 
                     WHERE session_id = ?
                     ORDER BY timestamp DESC LIMIT ?''', (target_session, limit))
        rows = c.fetchall()
        conn.close()
        
        hits = []
        for row in rows:
            # FIX: Hier war ein conn.close() im Loop, das zu Fehlern führt.
            # Einfach nur parsen:
            hits.append(json.loads(row["data"]))
            
        return hits
    
    def get_recent_logs(self, limit: int = 1000, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        target_session = session_id or self.current_session_id
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''SELECT level, message, timestamp FROM server_logs 
                     WHERE session_id = ?
                     ORDER BY timestamp ASC LIMIT ?''', (target_session, limit)) # ASC für Logs (chronologisch)
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]

# Globale Instanz
persistence = TUIPersistence()