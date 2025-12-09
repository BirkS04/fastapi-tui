"""
Utility functions for FastAPI exception handlers with TUI logging support.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from starlette.requests import Request
from fastapi.responses import JSONResponse

# NEU: Config importieren
from .config import get_config

from .loggers.runtime_logger import (
    log_queue_ctx, 
    request_id_ctx, 
    runtime_logs_ctx, 
    get_runtime_logs,
    add_runtime_log
)
from .loggers.exception_logger import (
    capture_exception,
    get_error_response_detail,
    # is_dev_mode entfernt
    ExceptionInfo
)


def restore_tui_context(request: Request) -> bool:
    """
    Restores TUI context variables from request.state if available.
    """
    if not hasattr(request.state, "tui_log_queue"):
        return False
    
    try:
        current_queue = log_queue_ctx.get()
        if current_queue is None:
            log_queue_ctx.set(request.state.tui_log_queue)
            request_id_ctx.set(request.state.tui_request_id)
            runtime_logs_ctx.set(request.state.tui_runtime_logs)
            return True
        else:
            return False
    except Exception as e:
        print(f"[TUI] Error restoring context: {e}")
        return False


def send_exception_to_tui(
    request: Request,
    exc_info: ExceptionInfo,
    error_content: Dict[str, Any],
    status_code: int = 500
) -> None:
    """
    Sends exception and request completion update to TUI queue.
    """
    if not (hasattr(request.state, "tui_log_queue") and hasattr(request.state, "tui_request_id")):
        return
    
    try:
        queue = request.state.tui_log_queue
        req_id = request.state.tui_request_id
        start_time = getattr(request.state, "tui_start_time", datetime.now())
        duration = (datetime.now() - start_time).total_seconds() * 1000
        
        # Send request completion update
        queue.put_nowait({
            "type": "request",
            "data": {
                "id": req_id,
                "endpoint": str(request.url.path),
                "method": request.method,
                "status_code": status_code,
                "duration_ms": duration,
                "response_body": error_content,
                "runtime_logs": get_runtime_logs(),
                "completed": True,
            }
        })
        
    except Exception as e:
        print(f"[TUI] Error updating TUI request status: {e}")


def build_error_response(
    exc: Exception,
    exc_info: ExceptionInfo,
    include_traceback: bool = None
) -> Dict[str, Any]:
    """
    Builds error response content based on config (enable_exceptions).
    """
    import traceback
    
    # NEU: Config nutzen statt is_dev_mode()
    config = get_config()
    
    if include_traceback is None:
        include_traceback = config.enable_exceptions
    
    error_content = {
        "error": "Internal Server Error",
        "detail": get_error_response_detail(exc), # Das nutzt intern auch schon config
        # Exception Type nur anzeigen, wenn Exceptions aktiviert sind
        "exception_type": exc_info.exception_type if config.enable_exceptions else None
    }
    
    if include_traceback:
        error_content["traceback"] = traceback.format_exc()
    
    return error_content


def create_cors_json_response(
    content: Dict[str, Any],
    status_code: int = 500,
    cors_origins: str = "*"
) -> JSONResponse:
    """
    Creates a JSONResponse with CORS headers.
    """
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={
            "Access-Control-Allow-Origin": cors_origins,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


def handle_exception_with_tui(
    request: Request,
    exc: Exception,
    status_code: int = 500,
    error_message: str = "Internal Server Error",
    log_to_runtime: bool = True
) -> JSONResponse:
    """
    Complete exception handling pipeline with TUI logging.
    """
    # Step 1: Restore context
    restore_tui_context(request)
    
    # Step 2: Log to runtime (optional)
    if log_to_runtime:
        add_runtime_log(f"Exception from Handler: {exc}")
    
    # Step 3: Capture exception
    exc_info = capture_exception(
        exc,
        endpoint=str(request.url.path),
        method=request.method
    )
    
    # Step 4: Build error response
    error_content = build_error_response(exc, exc_info)
    error_content["error"] = error_message  # Override default message
    
    # Step 5: Send to TUI
    send_exception_to_tui(request, exc_info, error_content, status_code)
    
    # Step 6: Return response
    return create_cors_json_response(error_content, status_code)