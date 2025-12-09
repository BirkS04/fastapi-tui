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
from ..config import get_config  # Import der Config-Logik

class TUIPersistence:
    def __init__(self):
        # 1. Config laden
        self.config = get_config()
        
        # 2. Config Loggen (wie gewünscht)
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("[PERSISTENCE] Initializing...")
        print(f"[PERSISTENCE] Full Config Payload: {self.config.to_json_payload()}")
        print(f"[PERSISTENCE] Enable Persistence: {self.config.enable_persistence}")
        print(f"[PERSISTENCE] DB Path: {self.config.db_path}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # 3. Werte setzen
        self.db_path = self.config.db_path
        self.enabled = self.config.enable_persistence
        self.current_session_id = None
        
        # 4. Nur starten, wenn aktiviert
        if self.enabled:
            self._init_db()
            self.start_new_session()
        else:
            self.current_session_id = "disabled"
    
    def _init_db(self):
        """Initialisiert die Datenbank-Tabellen"""
        if not self.enabled:
            return

        try:
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
            
            # Migration check
            try:
                c.execute("SELECT session_id FROM endpoint_hits LIMIT 1")
            except sqlite3.OperationalError:
                print("[PERSISTENCE] Upgrading DB schema (dropping old tables)...")
                c.execute("DROP TABLE IF EXISTS endpoint_hits")
                c.execute("DROP TABLE IF EXISTS server_logs")
                # Re-create logic would happen on next run or duplicate here, 
                # simplified for brevity as create if not exists handles it.
                
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PERSISTENCE] Error initializing DB: {e}")

    def start_new_session(self):
        """Startet eine neue Session"""
        if not self.enabled:
            return "disabled"

        self.current_session_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT INTO sessions (id, start_time, name) VALUES (?, ?, ?)",
                      (self.current_session_id, start_time, f"Session {start_time.strftime('%Y-%m-%d %H:%M')}"))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PERSISTENCE] Error starting session: {e}")
            
        return self.current_session_id

    def get_sessions(self) -> List[Dict[str, Any]]:
        """Gibt alle Sessions zurück"""
        if not self.enabled:
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM sessions ORDER BY start_time DESC")
            rows = c.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            return []
    
    def delete_session(self, session_id: str):
        """Löscht eine Session und ihre Daten"""
        if not self.enabled:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("DELETE FROM endpoint_hits WHERE session_id = ?", (session_id,))
            c.execute("DELETE FROM server_logs WHERE session_id = ?", (session_id,))
            c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[PERSISTENCE] Error deleting session: {e}")

    def save_hit(self, hit_data: Dict[str, Any]):
        if not self.enabled:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Ensure ID
            if "id" not in hit_data:
                hit_data["id"] = str(uuid.uuid4())
                
            c.execute('''INSERT OR REPLACE INTO endpoint_hits 
                         (id, session_id, endpoint, method, status_code, duration_ms, timestamp, data)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (hit_data["id"], self.current_session_id, hit_data.get("endpoint"), hit_data.get("method"),
                       hit_data.get("status_code"), hit_data.get("duration_ms"), 
                       hit_data.get("timestamp"), json.dumps(hit_data, default=str)))
            conn.commit()
            conn.close()
        except Exception as e:
            # Silent fail to not crash app, but maybe log to stderr
            # print(f"[PERSISTENCE] Error saving hit: {e}")
            pass

    def save_log(self, level: str, message: str, timestamp: datetime):
        if not self.enabled:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT INTO server_logs (session_id, level, message, timestamp) VALUES (?, ?, ?, ?)",
                      (self.current_session_id, level, message, timestamp))
            conn.commit()
            conn.close()
        except Exception:
            pass
        
    def get_recent_hits(self, limit: int = 100, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        try:
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
                hits.append(json.loads(row["data"]))
                
            return hits
        except Exception:
            return []
    
    def get_recent_logs(self, limit: int = 1000, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        try:
            target_session = session_id or self.current_session_id
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT level, message, timestamp FROM server_logs 
                         WHERE session_id = ?
                         ORDER BY timestamp ASC LIMIT ?''', (target_session, limit))
            rows = c.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            return []

# --- LAZY LOADING PATTERN ---
# Wir erstellen die Instanz erst, wenn sie gebraucht wird.
# Das verhindert Probleme beim Import und stellt sicher, dass die Config bereit ist.

_persistence_instance: Optional[TUIPersistence] = None

def get_persistence() -> TUIPersistence:
    global _persistence_instance
    if _persistence_instance is None:
        _persistence_instance = TUIPersistence()
    return _persistence_instance

