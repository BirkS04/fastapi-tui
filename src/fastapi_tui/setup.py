import sys
from typing import Optional, Callable, TYPE_CHECKING
from .config import TUIConfig, set_config

if TYPE_CHECKING:
    from fastapi import FastAPI

def with_tui(
    app: Optional["FastAPI"] = None,
    config: Optional[TUIConfig] = None,
    app_factory: Optional[Callable] = None,
    app_module: str = "app.main:app",  # Standard angepasst
    host: str = "127.0.0.1",
    port: int = 8000
) -> None:
    """
    Main entry point.
    """
    if config is None:
        config = TUIConfig.from_cli()
        config.host = host
        config.port = port
    
    set_config(config)
    
    # --- FALL 1: TUI Modus ---
    if "--tui" in sys.argv:
        from .runner import run_tui
        
        run_tui(
            app=app,                # NEU: App Instanz weitergeben
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
    
    # Wir nehmen die Instanz oder die Factory
    app_instance = app
    if app_instance is None and app_factory is not None:
        app_instance = app_factory()
    
    if app_instance is None:
        # Fallback auf Import-String
        uvicorn.run(app_module, host=host, port=port)
    else:
        uvicorn.run(app_instance, host=host, port=port)