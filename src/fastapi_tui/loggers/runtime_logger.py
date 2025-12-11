import contextvars
from typing import List, Any, Optional
from queue import Queue
from ..config import get_config

# ContextVars mit Defaults
runtime_logs_ctx = contextvars.ContextVar("runtime_logs", default=[])
request_id_ctx = contextvars.ContextVar("request_id", default=None)
log_queue_ctx = contextvars.ContextVar("log_queue", default=None)

def add_runtime_log(log: Any):
    """
    Adds a log entry to the current request's runtime logs.
    Safe to call in production (will do nothing if TUI is not active).
    """
    # 1. PERFORMANCE CHECK (Production Safety)
    # Wir holen direkt die Queue aus dem Context.
    # In Production (ohne Middleware) ist der Wert 'None' (der Default).
    # Das ist der schnellste mögliche Check in Python.
    queue = log_queue_ctx.get()
    if queue is None:
        return

    # 2. Config Check
    # Nur wenn eine Queue da ist, laden wir die Config.
    config = get_config()
    if not config.enable_runtime_logs:
        return

    # 3. Heavy Lifting (Nur im Dev Mode)
    # Erst jetzt machen wir die "teuren" Dinge wie Listen kopieren oder Daten maskieren.
    try:
        request_id = request_id_ctx.get()
        
        # Wenn wir keine Request ID haben, können wir es nicht zuordnen
        if request_id is None:
            return

        # Daten maskieren (kann bei großen Objekten dauern, daher erst hier)
        scrubbed_log = config.scrub_data(log)
        
        # Log zur lokalen Liste hinzufügen (für die Anzeige im Request-Detail später)
        logs = runtime_logs_ctx.get()
        logs.append(scrubbed_log)
        
        # Echtzeit-Update an die TUI senden
        queue.put_nowait({
            "type": "runtime_log_update",
            "data": {
                "request_id": request_id,
                "log": scrubbed_log,
                "all_logs": list(logs)
            }
        })
    except (LookupError, Exception):
        pass

def get_runtime_logs() -> List[Any]:
    try:
        return runtime_logs_ctx.get()
    except LookupError:
        return []