import contextvars
from typing import List, Any, Optional
from queue import Queue

# ContextVars for request-scoped data
runtime_logs_ctx = contextvars.ContextVar("runtime_logs", default=[])
request_id_ctx = contextvars.ContextVar("request_id", default=None)
log_queue_ctx = contextvars.ContextVar("log_queue", default=None)

def add_runtime_log(log: Any):
    """
    Adds a log entry to the current request's runtime logs.
    The log can be any serializable object (str, dict, list, etc.).
    Also sends the log immediately to the TUI if queue is available.
    """
    try:
        logs = runtime_logs_ctx.get()
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
                    "all_logs": list(logs)  # Send all logs for consistency
                }
            })
    except LookupError:
        # Fallback if context is not initialized (e.g. outside request)
        pass

def get_runtime_logs() -> List[Any]:
    """
    Returns the list of runtime logs for the current request.
    """
    try:
        return runtime_logs_ctx.get()
    except LookupError:
        return []
