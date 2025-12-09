# app/utils/tui/loggers/server_logger.py
from datetime import datetime
from multiprocessing import Queue

# Globale Variable, die die Queue hält
_log_queue: Queue = None

def init_logger(queue: Queue):
    """Wird beim Start von run_fastapi aufgerufen, um die Queue zu speichern."""
    global _log_queue
    _log_queue = queue

def write_server_log(message: str, level: str = "INFO"):
    """
    Diese Funktion sendet die Nachricht sicher an das TUI Log Window.
    """
    if _log_queue is not None:
        try:
            _log_queue.put_nowait({
                "type": "log",
                "data": {
                    "level": level,
                    "message": str(message),
                    "timestamp": datetime.now()
                }
            })
        except Exception as e:
            # Falls Queue voll ist oder Fehler auftritt
            pass
    else:
        # Fallback
        print(f"[FALLBACK LOG] {level}: {message}")
