"""
TUI Middleware - Request Logger
"""

import json
import uuid
import re
from datetime import datetime
from typing import Any, Dict, Optional
from multiprocessing import Queue as MPQueue

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match

# NEU: Config importieren
from ..config import get_config

class TUIMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, queue: MPQueue):
        super().__init__(app)
        self.queue = queue
        # NEU: Config laden
        self.config = get_config()
    
    async def dispatch(self, request: Request, call_next):
        # NEU: Prüfen ob Request geloggt werden soll
        if not self.config.should_log_request(request.url.path, request.method):
            return await call_next(request)

        request_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        from ..loggers.runtime_logger import runtime_logs_ctx, request_id_ctx, log_queue_ctx, get_runtime_logs
        
        logs_token = runtime_logs_ctx.set([])
        request_id_token = request_id_ctx.set(request_id)
        queue_token = log_queue_ctx.set(self.queue)
        
        request.state.tui_request_id = request_id
        request.state.tui_start_time = start_time
        request.state.tui_log_queue = self.queue
        
        try:
            query_params = dict(request.query_params) if request.query_params else None
            
            # NEU: Body maskieren
            raw_body = await self._capture_request_body(request)
            request_body = self.config.scrub_data(raw_body) if raw_body else None
            
            # NEU: Headers maskieren
            request_headers = self.config.scrub_headers(self._capture_headers(request))
            
            endpoint_path = self._get_endpoint_path(request)
            
            self._send_pending_event(
                request_id=request_id,
                endpoint=endpoint_path,
                method=request.method,
                client=request.client.host if request.client else "unknown",
                timestamp=start_time,
                query_params=query_params,
                request_body=request_body,
                request_headers=request_headers
            )
            
            try:
                response = await call_next(request)
            except Exception as exc:
                from fastapi_tui.exception_handler_utils import handle_exception_with_tui 
                response = handle_exception_with_tui(
                    request, 
                    exc,
                    status_code=500,
                    error_message="Critical Internal Error (Middleware Caught)",
                    log_to_runtime=True
                )

            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # NEU: Response Body maskieren (falls aktiviert)
            response_body = None
            if self.config.enable_response_body:
                raw_res_body, response = await self._capture_response_body(response)
                response_body = self.config.scrub_data(raw_res_body) if raw_res_body else None
            else:
                response_body = "<disabled>"
            
            self._send_completed_event(
                request_id=request_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration,
                client=request.client.host if request.client else "unknown",
                timestamp=start_time,
                query_params=query_params,
                request_body=request_body,
                request_headers=request_headers,
                response_body=response_body,
                runtime_logs=get_runtime_logs()
            )
            
            return response
            
        finally:
            current_logs = get_runtime_logs()
            request.state.tui_runtime_logs = current_logs
            
            runtime_logs_ctx.reset(logs_token)
            request_id_ctx.reset(request_id_token)
            log_queue_ctx.reset(queue_token)
    
    async def _capture_request_body(self, request: Request) -> Optional[Dict[str, Any]]:
        """Capture and parse request body"""
        if request.method not in ["POST", "PUT", "PATCH"]:
            return None
        
        try:
            body_bytes = await request.body()
            if not body_bytes:
                return None
            
            content_type = request.headers.get("content-type", "")
            
            if "application/json" in content_type:
                result = json.loads(body_bytes.decode())
            elif "application/x-www-form-urlencoded" in content_type:
                result = self._parse_urlencoded(body_bytes)
            elif "multipart/form-data" in content_type:
                result = self._parse_multipart(body_bytes, content_type)
            else:
                result = {"_note": f"binary data ({content_type})", "size": len(body_bytes)}
            
            # Make body available again for the handler
            async def receive():
                return {"type": "http.request", "body": body_bytes}
            request._receive = receive
            
            return result
            
        except Exception:
            return None
    
    def _parse_urlencoded(self, body_bytes: bytes) -> Dict[str, Any]:
        """Parse URL-encoded form data"""
        try:
            from urllib.parse import parse_qs
            parsed = parse_qs(body_bytes.decode())
            return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        except Exception:
            return {"_note": "urlencoded (unparseable)", "size": len(body_bytes)}
    
    def _parse_multipart(self, body_bytes: bytes, content_type: str) -> Dict[str, Any]:
        """Parse multipart form data"""
        try:
            body_str = body_bytes.decode('utf-8', errors='replace')
            boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
            
            if not boundary_match:
                return {"_note": "multipart/form-data", "size": len(body_bytes)}
            
            boundary = boundary_match.group(1)
            parts = body_str.split(f'--{boundary}')
            fields = {}
            
            for part in parts:
                if 'Content-Disposition' not in part:
                    continue
                    
                name_match = re.search(r'name="([^"]+)"', part)
                filename_match = re.search(r'filename="([^"]+)"', part)
                
                if name_match:
                    field_name = name_match.group(1)
                    if filename_match:
                        fields[field_name] = f"[FILE: {filename_match.group(1)}]"
                    else:
                        value_parts = part.split('\r\n\r\n', 1)
                        if len(value_parts) > 1:
                            value = value_parts[1].strip().rstrip('-').strip()
                            if len(value) > 200:
                                value = value[:200] + "..."
                            fields[field_name] = value
            
            return {"_type": "multipart/form-data", "fields": fields}
            
        except Exception:
            return {"_note": "multipart/form-data (parse error)", "size": len(body_bytes)}
    
    def _capture_headers(self, request: Request) -> Dict[str, str]:
        """Capture all headers (scrubbing happens later via config)"""
        return dict(request.headers)
    
    def _get_endpoint_path(self, request: Request) -> str:
        """Get the endpoint path, trying to match route templates"""
        try:
            for route in request.app.routes:
                match, _ = route.matches(request.scope)
                if match == Match.FULL:
                    return route.path
        except Exception:
            pass
        return request.url.path
    
    async def _capture_response_body(self, response: Response):
        """Capture response body if JSON"""
        response_body = None
        
        # 1. Content-Type Check
        if not response.headers.get("content-type", "").startswith("application/json"):
            return response_body, response
        
        # 2. Body Bytes sicher auslesen
        body_bytes = b""
        try:
            # Fall A: StreamingResponse (kommt oft aus call_next)
            if hasattr(response, "body_iterator"):
                async for chunk in response.body_iterator:
                    body_bytes += chunk
            # Fall B: Standard Response / JSONResponse (kommt aus unserem Exception Handler)
            else:
                body_bytes = response.body
        except Exception:
            # Fallback, falls Body nicht lesbar
            pass
        
        # 3. JSON Parsen
        try:
            if body_bytes:
                response_body = json.loads(body_bytes.decode())
        except Exception:
            pass
        
        # 4. Response neu erstellen (da wir den Stream/Body konsumiert haben)
        new_response = Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
        
        return response_body, new_response

    def _send_pending_event(self, **kwargs):
        """Send a pending request event to the queue"""
        try:
            self.queue.put_nowait({
                "type": "request",
                "data": {
                    "id": kwargs["request_id"],
                    "endpoint": kwargs["endpoint"],
                    "method": kwargs["method"],
                    "status_code": None,
                    "duration_ms": None,
                    "client": kwargs["client"],
                    "timestamp": kwargs["timestamp"],
                    "request_params": kwargs["query_params"],
                    "request_body": kwargs["request_body"],
                    "request_headers": kwargs["request_headers"],
                    "runtime_logs": [],
                    "pending": True,
                    "completed": False
                }
            })
        except Exception as e:
            print(f"[TUI] Error sending pending event: {e}")
    
    def _send_completed_event(self, **kwargs):
        """Send a completed request event to the queue"""
        try:
            self.queue.put_nowait({
                "type": "request",
                "data": {
                    "id": kwargs["request_id"],
                    "endpoint": kwargs["endpoint"],
                    "method": kwargs["method"],
                    "status_code": kwargs["status_code"],
                    "duration_ms": kwargs["duration_ms"],
                    "client": kwargs["client"],
                    "timestamp": kwargs["timestamp"],
                    "request_params": kwargs["query_params"],
                    "request_body": kwargs["request_body"],
                    "request_headers": kwargs["request_headers"],
                    "response_body": kwargs["response_body"],
                    "runtime_logs": kwargs["runtime_logs"],
                    "pending": False,
                    "completed": True
                }
            })
        except Exception as e:
            print(f"[TUI] Error sending completed event: {e}")
