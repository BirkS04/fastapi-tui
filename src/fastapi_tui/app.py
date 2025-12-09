"""
FastAPI TUI - Main Application

This module contains the FastAPITUI App class and related utilities.
For full functionality, the existing fastapi_tui.py is used.
This file adds the run_fastapi_process helper for the runner.
"""

# Import everything from the existing fastapi_tui module
from .fastapi_tui import (
    FastAPITUI,
    TUIManager,
    get_tui_manager
)

import uvicorn
from multiprocessing import Queue as MPQueue


def run_fastapi_process(queue: MPQueue, host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Run FastAPI in a subprocess with TUI logging.
    
    This is used by TUIRunner when reload=False.
    """
    from .loggers.server_logger import init_logger, write_server_log
    import sys
    
    try:
        # Initialize logger bridge
        init_logger(queue)
        write_server_log("FastAPI process started", "SYSTEM")
        
        # Redirect stdout/stderr to TUI
        class BridgeLogger:
            def write(self, msg):
                try:
                    if msg and msg.strip():
                        write_server_log(msg.strip(), "PRINT")
                except Exception:
                    pass
            def flush(self): 
                pass
            def isatty(self): 
                return False
        
        sys.stdout = BridgeLogger()
        sys.stderr = BridgeLogger()
        
        # Create app with queue
        from app.main import create_app
        app = create_app(queue)
        
        # Run uvicorn
        config = uvicorn.Config(app, host=host, port=port, log_config=None)
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None
        server.run()
        
    except Exception as e:
        import traceback
        error_msg = f"CRITICAL ERROR IN FASTAPI PROCESS:\n{e}\n\n{traceback.format_exc()}"
        with open("fastapi_startup_error.txt", "w") as f:
            f.write(error_msg)
        raise e


__all__ = [
    "FastAPITUI",
    "TUIManager", 
    "get_tui_manager",
    "run_fastapi_process"
]
