"""
Exception Logger - Captures exceptions with full context for TUI display.
Optimized for Zero-Overhead in Production.
"""

import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from queue import Queue

from .runtime_logger import log_queue_ctx, request_id_ctx
from ..config import get_config


class StackFrame(BaseModel):
    filename: str
    function: str
    lineno: int
    locals_preview: Dict[str, str] = Field(default_factory=dict)

class ExceptionInfo(BaseModel):
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    exception_type: str
    message: str
    traceback_str: str
    frames: List[StackFrame] = Field(default_factory=list)
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

def _safe_repr(value: Any, max_length: int = 100) -> str:
    try:
        r = repr(value)
        if len(r) > max_length:
            return r[:max_length - 3] + "..."
        return r
    except Exception:
        return f"<{type(value).__name__}: repr failed>"

def _extract_locals(frame_locals: Dict[str, Any], max_vars: int = 10) -> Dict[str, str]:
    """Extract and sanitize local variables from a frame."""
    config = get_config()
    result = {}
    count = 0
    
    for name, value in frame_locals.items():
        if count >= max_vars:
            break
        
        if name.startswith('_'):
            continue
        
        if name.lower() in config.mask_body_fields:
            result[name] = "***MASKED***"
        else:
            result[name] = _safe_repr(value)
        
        count += 1
    
    return result

def capture_exception(
    exc: Exception,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    log_queue: Optional[Queue] = None
) -> ExceptionInfo:
    """
    Captures an exception.
    
    PERFORMANCE NOTE:
    In Production (when log_queue is None), this function skips 
    expensive stack trace analysis and variable extraction.
    """
    config = get_config()
    
    # 1. Queue ermitteln (Check für Production Mode)
    queue = log_queue
    if queue is None:
        try:
            queue = log_queue_ctx.get()
        except LookupError:
            queue = None

    # 2. Request ID holen (falls vorhanden)
    try:
        request_id = request_id_ctx.get()
    except LookupError:
        request_id = None


    should_capture_details = (queue is not None) and config.enable_exceptions

    # --- FAST PATH (Production) ---
    if not should_capture_details:

        return ExceptionInfo(
            exception_type=type(exc).__name__,
            message=str(exc),
            traceback_str="Traceback not captured (TUI disabled)", 
            frames=[], # Leere Liste = Keine Performance Kosten
            request_id=request_id,
            endpoint=endpoint,
            method=method
        )

    # --- SLOW PATH (Development / TUI Active) ---

    
    exc_type, exc_value, exc_traceback = sys.exc_info()
    frames = []
    
    if exc_traceback:
        tb = exc_traceback
        while tb is not None:
            frame = tb.tb_frame

            locals_preview = _extract_locals(dict(frame.f_locals))
            frames.append(StackFrame(
                filename=frame.f_code.co_filename,
                function=frame.f_code.co_name,
                lineno=tb.tb_lineno,
                locals_preview=locals_preview
            ))
            tb = tb.tb_next
    
    exc_info = ExceptionInfo(
        exception_type=exc_type.__name__ if exc_type else type(exc).__name__,
        message=str(exc),
        traceback_str=traceback.format_exc(), # Teuer: String formatierung
        frames=frames,
        request_id=request_id,
        endpoint=endpoint,
        method=method
    )
    
    # An TUI senden
    try:
        queue.put_nowait({
            "type": "exception",
            "data": exc_info.model_dump()
        })
    except Exception:
        pass
    
    return exc_info

def get_error_response_detail(exc: Exception) -> str:
    """Returns appropriate error detail based on mode."""
    config = get_config()
    # Wenn Exceptions aktiviert sind (Dev Mode), zeigen wir Details
    if config.enable_exceptions:
        return str(exc)
    return "An internal error occurred. Please try again later."