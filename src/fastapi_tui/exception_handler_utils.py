"""
Utility functions for FastAPI exception handlers with TUI logging support.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from starlette.requests import Request
from fastapi.responses import JSONResponse

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
    is_dev_mode,
    ExceptionInfo
)


def restore_tui_context(request: Request) -> bool:
    """
    Restores TUI context variables from request.state if available.
    
    Args:
        request: The FastAPI/Starlette Request object
        
    Returns:
        bool: True if context was restored, False otherwise
    """
    if not hasattr(request.state, "tui_log_queue"):
        return False
    
    try:
        current_queue = log_queue_ctx.get()
        if current_queue is None:
            # print(f"[TUI] Restoring context from request.state. Queue: {request.state.tui_log_queue is not None}")
            log_queue_ctx.set(request.state.tui_log_queue)
            request_id_ctx.set(request.state.tui_request_id)
            runtime_logs_ctx.set(request.state.tui_runtime_logs)
            return True
        else:
            print(f"[TUI] Context already has queue: {current_queue is not None}")
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
    
    Args:
        request: The FastAPI/Starlette Request object
        exc_info: ExceptionInfo object from capture_exception()
        error_content: Error response content dict
        status_code: HTTP status code (default: 500)
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
    Builds error response content based on dev/prod mode.
    
    Args:
        exc: The original exception
        exc_info: ExceptionInfo object from capture_exception()
        include_traceback: Override auto-detection of dev mode
        
    Returns:
        Dict with error response content
    """
    import traceback
    
    if include_traceback is None:
        include_traceback = is_dev_mode()
    
    error_content = {
        "error": "Internal Server Error",
        "detail": get_error_response_detail(exc),
        "exception_type": exc_info.exception_type if is_dev_mode() else None
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
    
    Args:
        content: Response content dict
        status_code: HTTP status code
        cors_origins: CORS origins (default: "*")
        
    Returns:
        JSONResponse with CORS headers
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
    
    This is the high-level function that combines all steps:
    1. Restore TUI context
    2. Log to runtime logs (optional)
    3. Capture exception with full context
    4. Build error response
    5. Send to TUI queue
    6. Return JSON response with CORS
    
    Args:
        request: The FastAPI/Starlette Request object
        exc: The exception to handle
        status_code: HTTP status code (default: 500)
        error_message: Custom error message (default: "Internal Server Error")
        log_to_runtime: Whether to add runtime log entry (default: True)
        
    Returns:
        JSONResponse with error details and CORS headers
    
    Example:
        @app.exception_handler(ValueError)
        async def value_error_handler(request: Request, exc: ValueError):
            return handle_exception_with_tui(
                request, exc, 
                status_code=400, 
                error_message="Invalid input"
            )
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