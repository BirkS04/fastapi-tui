"""
FastAPI TUI Monitoring System

A comprehensive Terminal User Interface for FastAPI applications.

## Quick Start

The simplest way to add TUI monitoring:

```python
from fastapi import FastAPI
from fastapi_tui import with_tui

app = FastAPI()
# ... configure your app ...

if __name__ == "__main__":
    with_tui(app)
```

Then run with:
```bash
python -m app.main --tui          # Normal mode
python -m app.main --tui --dev    # With hot-reload
```

## Configuration

```python
from fastapi_tui import TUIConfig, with_tui

config = TUIConfig(
    port=8080,
    enable_exceptions=True,
    log_level=LogLevel.DEBUG,
    exclude_paths={"/health", "/metrics"}
)
with_tui(app, config=config)
```
"""

# Config
from .config import TUIConfig, LogLevel, get_config, set_config

# Setup - Main entry point
from .setup import with_tui

# Configure TUI
from .configure_tui import configure_tui, create_tui_app

# Core Models
from .core import (
    EventType,
    EndpointHit,
    CustomEvent,
    EndpointStats,
    TUIEvent,
    create_hit_id,
    create_pending_hit,
    create_completed_hit,
    create_custom_event,
)

# Middleware
from .middleware import TUIMiddleware

# App
from .app import FastAPITUI, TUIManager, get_tui_manager

# Runner
from .runner import TUIRunner, run_tui

# Persistence
from .persistence import TUIPersistence

from .configure_tui import configure_tui

# Widgets (for customization)
from .widgets import (
    AutoScrollLog,
    JSONViewer,
    RuntimeLogsViewer,
    EndpointList,
    RequestViewer,
    RequestInspector,
    StatsDashboard,
    ExceptionViewer,
)

# Handlers (utilities)
from .handlers import (
    format_duration,
    format_log_line,
    get_stats_color,
)

# Loggers
# Loggers
from .loggers.server_logger import init_logger, write_server_log
from .loggers.runtime_logger import add_runtime_log, get_runtime_logs
from .loggers.exception_logger import capture_exception, is_dev_mode, get_error_response_detail

__all__ = [
    # Config
    "TUIConfig",
    "LogLevel",
    "get_config",
    "set_config",
    # Setup (main entry points)
    "with_tui",
    # Configure TUI
    "configure_tui",
    "create_tui_app",
    # Core Models
    "EventType",
    "EndpointHit",
    "CustomEvent",
    "EndpointStats",
    "TUIEvent",
    "create_hit_id",
    "create_pending_hit",
    "create_completed_hit",
    "create_custom_event",
    # Middleware
    "TUIMiddleware",
    # App
    "FastAPITUI",
    "TUIManager",
    "get_tui_manager",
    # Runner
    "TUIRunner",
    "run_tui",
    # Persistence
    "TUIPersistence",
    "persistence",
    # Widgets
    "AutoScrollLog",
    "JSONViewer",
    "RuntimeLogsViewer",
    "EndpointList",
    "RequestViewer",
    "RequestInspector",
    "StatsDashboard",
    "ExceptionViewer",
    # Utilities
    "format_duration",
    "format_log_line",
    "get_stats_color",
    # Loggers
    "init_logger",
    "write_server_log",
    "add_runtime_log",
    "get_runtime_logs",
    "capture_exception",
    "is_dev_mode",
    "get_error_response_detail",
]
