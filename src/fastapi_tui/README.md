# FastAPI TUI Monitor

Ein leistungsfähiges Terminal User Interface (TUI) für FastAPI-Anwendungen.

## Quick Start

```python
from fastapi import FastAPI
from app.utils.tui import with_tui

app = FastAPI()

if __name__ == "__main__":
    with_tui(app)  # Das ist alles!
```

**Starten:**
```bash
python -m app.main --tui          # Normal
python -m app.main --tui --dev    # Mit Hot-Reload
```

---

## Features

- 📊 **Request Monitoring** - Alle HTTP Requests in Echtzeit
- 🔍 **Request Inspector** - Details zu jedem Request (Body, Headers, Response)
- 📝 **Runtime Logs** - Custom Logs während der Request-Verarbeitung
- ⚠️ **Exception Tracking** - Exceptions mit Full Traceback
- 📈 **Stats Dashboard** - Statistiken pro Endpoint
- 💾 **Persistence** - SQLite-basierte Session-Persistenz

---

## Configuration

```python
from app.utils.tui import TUIConfig, with_tui, LogLevel

config = TUIConfig(
    # Server
    port=8080,
    host="0.0.0.0",
    
    # Hot-Reload
    reload=True,
    reload_dirs=["app", "lib"],
    
    # Features
    enable_exceptions=True,
    enable_request_logging=True,
    enable_response_body=True,
    enable_runtime_logs=True,
    enable_stats=True,
    enable_persistence=True,
    
    # Logging
    log_level=LogLevel.DEBUG,
    
    # UI
    show_sidebar=True,
    show_stats_panel=True,
    max_hits_display=100,
    
    # Filtering
    exclude_paths={"/health", "/metrics"},
    exclude_methods={"OPTIONS"},
    
    # Security
    mask_headers={"authorization", "x-api-key"},
    mask_body_fields={"password", "secret"},
)

with_tui(app, config=config)
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TUI_HOST` | `0.0.0.0` | Server host |
| `TUI_PORT` | `8000` | Server port |
| `TUI_RELOAD` | `false` | Enable hot-reload |
| `TUI_EXCEPTIONS` | `true` | Enable exception tracking |
| `TUI_LOG_LEVEL` | `info` | Log level |
| `TUI_DB_PATH` | `tui_events.db` | SQLite path |

### CLI Flags

| Flag | Description |
|------|-------------|
| `--tui` | Enable TUI mode |
| `--dev` / `--reload` | Enable hot-reload |
| `--port=XXXX` | Set server port |
| `--host=X.X.X.X` | Set server host |

---

## API Reference

### Main Entry Points

#### `with_tui(app, config=None)`
One-liner to add TUI support. Handles everything automatically.

```python
with_tui(app)  # Minimal
with_tui(app, config=TUIConfig(port=8080))  # Mit Config
```

#### `run_with_tui(app_factory, app_module)`
Alternative für Factory-Pattern.

```python
run_with_tui(create_app, "app.main:app_for_reload")
```

### Runtime Logging

```python
from app.utils.tui import add_runtime_log

@app.post("/example")
async def example():
    add_runtime_log({"step": "starting", "data": {...}})
    # ... processing ...
    add_runtime_log({"step": "completed", "result": {...}})
    return {"ok": True}
```

### Exception Tracking

```python
from app.utils.tui import capture_exception

try:
    dangerous_operation()
except Exception as e:
    capture_exception(e, endpoint="/api/example", method="POST")
    return {"error": str(e)}
```

---

## Package Structure

```
app/utils/tui/
├── __init__.py          # Public API
├── config.py            # TUIConfig
├── setup.py             # with_tui(), run_with_tui()
├── app.py               # FastAPITUI
├── runner.py            # TUIRunner
├── loggers/
│   ├── server_logger.py     # write_server_log, init_logger
│   ├── runtime_logger.py    # add_runtime_log, get_runtime_logs
│   └── exception_logger.py  # capture_exception, is_dev_mode
├── core/
│   ├── models.py        # EndpointHit, CustomEvent, etc.
│   └── events.py        # Event utilities
├── middleware/
│   └── request_logger.py  # TUIMiddleware
├── handlers/
│   ├── hit_handler.py
│   ├── log_handler.py
│   ├── exception_handler.py
│   └── stats_handler.py
├── persistence/
│   └── sqlite.py
└── widgets/
    ├── auto_scroll_log.py
    ├── endpoint_list.py
    ├── request_viewer.py
    ├── request_inspector.py
    ├── json_viewer.py
    ├── stats_dashboard.py
    └── exception_viewer.py
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `s` | Toggle Stats Panel |
| `e` | Toggle Endpoint Sidebar |
| `r` | Refresh |

---

## Examples

### Minimal Setup
```python
from fastapi import FastAPI
from app.utils.tui import with_tui

app = FastAPI()

@app.get("/")
async def root():
    return {"hello": "world"}

if __name__ == "__main__":
    with_tui(app)
```

### Mit Logging
```python
from app.utils.tui import add_runtime_log

@app.post("/process")
async def process(data: dict):
    add_runtime_log({"event": "received", "size": len(data)})
    
    result = await heavy_processing(data)
    
    add_runtime_log({"event": "completed", "result_size": len(result)})
    return result
```

### Custom Config
```python
config = TUIConfig(
    port=3000,
    enable_response_body=False,  # Große Responses nicht loggen
    exclude_paths={"/health", "/ws"},
    mask_body_fields={"password", "credit_card"}
)
with_tui(app, config=config)
```
