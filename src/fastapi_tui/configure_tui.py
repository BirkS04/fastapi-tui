import sys
import logging
from datetime import datetime
from multiprocessing import Queue as MPQueue
from fastapi import FastAPI

# Imports aus deinem bestehenden TUI-Package
from .loggers.server_logger import init_logger
from .ipc import get_queue_client
from .middleware import TUIMiddleware

def setup_tui_logging(queue: MPQueue):
    """
    Richtet Logging ein.
    Entfernt Standard-Handler um Duplikate und TUI-Glitches zu vermeiden.
    """
    if not queue:
        return

    # 1. Basis Logger initialisieren
    init_logger(queue)
    
    def send_log_to_queue(msg: str, level: str, log_type: str = None):
        try:
            queue.put({
                "type": "log",
                "data": {
                    "level": level,
                    "message": msg,
                    "timestamp": datetime.now(),
                    "type": log_type or level
                }
            })
        except Exception:
            pass

    # 2. Stdout/Stderr umleiten (BridgeLogger)
    class BridgeLogger:
        def write(self, msg):
            try:
                if msg and msg.strip():
                    send_log_to_queue(msg.strip(), "PRINT", "PRINT")
            except Exception:
                pass 
        def flush(self): pass
        def isatty(self): return False
        
    sys.stdout = BridgeLogger()
    sys.stderr = BridgeLogger()

    # 3. Logging Handler für Uvicorn & FastAPI Logger
    class TUILogHandler(logging.Handler):
        def emit(self, record):
            try:
                msg = self.format(record)
                log_type = "UVICORN"
                if "access" in record.name:
                    log_type = "ACCESS"
                elif "error" in record.name:
                    log_type = "ERROR"
                
                send_log_to_queue(msg, record.levelname, log_type)
            except Exception:
                pass

    tui_handler = TUILogHandler()
    tui_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s')
    tui_handler.setFormatter(formatter)

    # 4. Bestehende Handler patchen
    loggers_to_patch = ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]
    
    for logger_name in loggers_to_patch:
        logger = logging.getLogger(logger_name)
        logger.handlers = [tui_handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

def create_tui_app(app: FastAPI) -> FastAPI:
    """
    Instrumentiert eine FastAPI-Anwendung mit der TUI-Middleware und Logging.
    Gibt die modifizierte App zurück, um Chaining zu ermöglichen.
    
    Usage:
        app = FastAPI()
        app = create_tui_app(app)
    """
    # Queue holen (nur vorhanden, wenn via TUI Runner gestartet)
    log_queue = get_queue_client()
    
    if log_queue:
        # 1. Logging Setup aufrufen (Stdout redirection etc.)
        setup_tui_logging(log_queue)
        
        # 2. Middleware hinzufügen
        app.add_middleware(TUIMiddleware, queue=log_queue)
        
    # 3. App zurückgeben
    return app

# Alias für Rückwärtskompatibilität
configure_tui = create_tui_app