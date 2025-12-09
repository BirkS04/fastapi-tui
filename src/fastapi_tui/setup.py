import sys
from typing import Optional, Callable, TYPE_CHECKING
from .config import TUIConfig, set_config

if TYPE_CHECKING:
    from fastapi import FastAPI

def with_tui(
    app: Optional["FastAPI"] = None,
    config: Optional[TUIConfig] = None,
    app_factory: Optional[Callable] = None,
    app_module: str = "app.main:app",
    host: str = "127.0.0.1",
    port: int = 8000
) -> None:
    """
    Main entry point.
    """
    if config is None:
        config = TUIConfig.from_cli()
        # Fallback auf Funktionsargumente, wenn nicht in CLI/Config
        if config.host == "0.0.0.0": config.host = host
        if config.port == 8000: config.port = port
    else:
        # WICHTIG: Auch wenn Config per Code übergeben wurde,
        # CLI Argumente (--reload, --port) müssen gewinnen!
        config.override_from_cli()
    
    set_config(config)
    
    # --- FALL 1: TUI Modus ---
    if "--tui" in sys.argv:
        from .runner import run_tui
        
        run_tui(
            app=app,
            app_factory=app_factory,
            app_module=app_module,
            # Wir nutzen jetzt strikt die Config als Source of Truth
            reload=config.reload,
            port=config.port,
            host=config.host
        )
        return

    # --- FALL 2: Standard Uvicorn Modus ---
    import uvicorn
    
    print(f"FastAPI läuft auf http://{config.host}:{config.port}")
    print("Starte mit --tui für TUI Monitor")
    
    app_instance = app
    if app_instance is None and app_factory is not None:
        app_instance = app_factory()
    
    if app_instance is None:
        uvicorn.run(app_module, host=config.host, port=config.port)
    else:
        uvicorn.run(app_instance, host=config.host, port=config.port)