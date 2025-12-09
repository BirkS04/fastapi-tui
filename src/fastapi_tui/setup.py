"""
TUI Setup - Simple API for integrating TUI with FastAPI
"""

import sys
from multiprocessing import Queue as MPQueue
from typing import Optional, Callable, TYPE_CHECKING
from .config import TUIConfig, set_config

if TYPE_CHECKING:
    from fastapi import FastAPI

def with_tui(
    app: Optional["FastAPI"] = None,
    config: Optional[TUIConfig] = None,
    app_factory: Optional[Callable] = None,
    app_module: str = "app.main:app_for_reload",
    host: str = "127.0.0.1",
    port: int = 8000
) -> None:
    """
    Main entry point.
    Entscheidet basierend auf sys.argv, ob die TUI oder der Standard-Server gestartet wird.
    """
    if config is None:
        config = TUIConfig.from_cli()
        # Überschreibe Config-Werte mit Funktionsargumenten, falls nötig
        config.host = host
        config.port = port
    
    set_config(config)
    
    # --- FALL 1: TUI Modus ---
    if "--tui" in sys.argv:
        from .runner import run_tui
        
        run_tui(
            app_factory=app_factory,
            app_module=app_module,
            reload=config.reload,
            port=config.port,
            host=config.host
        )
        return

    # --- FALL 2: Standard Uvicorn Modus (ohne TUI) ---
    import uvicorn
    
    print(f"FastAPI läuft auf http://{host}:{port}")
    print("Starte mit --tui für TUI Monitor")
    
    # Wir brauchen eine App-Instanz für Uvicorn
    app_instance = app
    if app_instance is None and app_factory is not None:
        app_instance = app_factory()
    
    if app_instance is None:
        # Fallback: Wenn weder App noch Factory übergeben wurden, 
        # versuchen wir den Import-String für Uvicorn zu nutzen (gut für Reload)
        uvicorn.run(app_module, host=host, port=port)
    else:
        # Standard Start mit Instanz
        uvicorn.run(app_instance, host=host, port=port)