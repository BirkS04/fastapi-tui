import sys
import logging
from datetime import datetime
from multiprocessing import Queue as MPQueue
from fastapi import FastAPI

from .loggers.server_logger import init_logger
from .ipc import get_queue_client
from .middleware import TUIMiddleware
# NEU: Config importieren
from .config import get_config

def setup_tui_logging(queue: MPQueue):
    """
    Richtet Logging ein (Queue + Optional File).
    """
    if not queue:
        return

    config = get_config() # NEU: Config laden
    
    # Level aus Config holen (z.B. "DEBUG" -> logging.DEBUG)
    target_level = getattr(logging, config.log_level.value.upper(), logging.INFO)

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

    # 2. Stdout/Stderr umleiten
    class BridgeLogger:
        def write(self, msg):
            try:
                if msg and msg.strip():
                    send_log_to_queue(msg.strip(), "PRINT", "PRINT")
            except Exception: pass 
        def flush(self): pass
        def isatty(self): return False
        
    sys.stdout = BridgeLogger()
    sys.stderr = BridgeLogger()

    # 3. TUI Handler (Queue)
    class TUILogHandler(logging.Handler):
        def emit(self, record):
            try:
                msg = self.format(record)
                log_type = "UVICORN"
                if "access" in record.name: log_type = "ACCESS"
                elif "error" in record.name: log_type = "ERROR"
                send_log_to_queue(msg, record.levelname, log_type)
            except Exception: pass

    tui_handler = TUILogHandler()
    tui_handler.setLevel(target_level) # NEU: Level aus Config
    formatter = logging.Formatter('%(message)s')
    tui_handler.setFormatter(formatter)
    
    handlers_list = [tui_handler]

    # 4. NEU: File Handler (wenn aktiviert)
    if config.log_to_file:
        try:
            file_handler = logging.FileHandler(config.log_file_path, mode='a', encoding='utf-8')
            file_handler.setLevel(target_level)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            handlers_list.append(file_handler)
        except Exception as e:
            print(f"[TUI] Error setting up file logging: {e}")

    # 5. Bestehende Handler patchen
    loggers_to_patch = ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]
    
    for logger_name in loggers_to_patch:
        logger = logging.getLogger(logger_name)
        logger.handlers = handlers_list # NEU: Liste mit TUI + File Handler
        logger.propagate = False
        logger.setLevel(target_level) # NEU: Level aus Config

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
        setup_tui_logging(log_queue)
        app.add_middleware(TUIMiddleware, queue=log_queue)
    return app

configure_tui = create_tui_app