import contextvars
from typing import List, Any, Optional
from queue import Queue
from ..config import get_config # NEU

# ContextVars for request-scoped data
runtime_logs_ctx = contextvars.ContextVar("runtime_logs", default=[])
request_id_ctx = contextvars.ContextVar("request_id", default=None)
log_queue_ctx = contextvars.ContextVar("log_queue", default=None)

def add_runtime_log(log: Any):
    """
    Adds a log entry to the current request's runtime logs.
    """
    config = get_config() # NEU
    
    # Wenn Runtime Logs deaktiviert sind, machen wir gar nichts
    if not config.enable_runtime_logs:
        return

    try:
        logs = runtime_logs_ctx.get()
        
        # NEU: Optional Daten maskieren (falls du das willst)
        log = config.scrub_data(log) 
        
        logs.append(log)
        
        # Send real-time update to TUI
        queue: Optional[Queue] = log_queue_ctx.get()
        request_id: Optional[str] = request_id_ctx.get()
        
        if queue and request_id:
            queue.put_nowait({
                "type": "runtime_log_update",
                "data": {
                    "request_id": request_id,
                    "log": log,
                    "all_logs": list(logs)
                }
            })
    except LookupError:
        pass

def get_runtime_logs() -> List[Any]:
    try:
        return runtime_logs_ctx.get()
    except LookupError:
        return []