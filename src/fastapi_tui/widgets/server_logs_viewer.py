"""
Server Logs Viewer - Structured view of all server logs with filtering
"""

from textual.containers import Container
from textual.widgets import TabbedContent, TabPane
from textual.app import ComposeResult
from datetime import datetime
from typing import Dict, Any, List

from .auto_scroll_log import AutoScrollLog


class ServerLogsViewer(Container):
    """
    Main container for server logs with filtered subtabs.
    
    Tabs:
    - All Logs: Everything
    - HTTP: Only request/response logs (INFO with POST/GET/etc)
    - Exceptions: Only ERROR/CRITICAL logs
    - System: Only SYSTEM logs (startup, shutdown, etc)
    - Application: Only UVICORN/PRINT logs (your custom logs)
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.all_logs: List[Dict[str, Any]] = []
    
    def compose(self) -> ComposeResult:
        """Create the tabbed structure"""
        with TabbedContent(id="server-logs-tabs"):
            with TabPane("All Logs", id="logs-all"):
                yield AutoScrollLog(id="log-all", highlight=True)
            
            with TabPane("HTTP", id="logs-http"):
                yield AutoScrollLog(id="log-http", highlight=True)
            
            with TabPane("Exceptions", id="logs-exceptions"):
                yield AutoScrollLog(id="log-exceptions", highlight=True)
            
            with TabPane("System", id="logs-system"):
                yield AutoScrollLog(id="log-system", highlight=True)
            
            with TabPane("Application", id="logs-application"):
                yield AutoScrollLog(id="log-application", highlight=True)
    
    def add_log(self, log_data: Dict[str, Any]) -> None:
        """
        Add a log entry and route it to appropriate tabs.
        
        Args:
            log_data: Dict with keys: timestamp, level, message, (optional) type
        """
        # Store in history
        self.all_logs.append(log_data)
        
        # Parse log data
        timestamp = log_data.get("timestamp")
        level = log_data.get("level", "INFO")
        message = log_data.get("message", "")
        log_type = log_data.get("type", level)  # Custom type or use level
        
        # Format timestamp
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp)
                ts_str = dt.strftime("%H:%M:%S")
            except:
                ts_str = timestamp
        elif isinstance(timestamp, datetime):
            ts_str = timestamp.strftime("%H:%M:%S")
        else:
            ts_str = datetime.now().strftime("%H:%M:%S")
        
        # Determine color based on level
        color = self._get_color_for_level(level)
        
        # Escape any Rich markup in the message itself to prevent conflicts
        safe_message = message.replace("[", "\\[").replace("]", "\\]")
        
        # Format the log line with proper Rich markup
        formatted_line = f"[{color}]\\[{ts_str}] \\[{level}] {safe_message}[/{color}]"
        
        # 1. Always add to "All Logs"
        try:
            log_all = self.query_one("#log-all", AutoScrollLog)
            log_all.write_line(formatted_line)
        except:
            pass  # Widget not mounted yet
        
        # 2. Route to specific tabs based on content
        self._route_to_http(formatted_line, message, level)
        self._route_to_exceptions(formatted_line, level)
        self._route_to_system(formatted_line, log_type, message)
        self._route_to_application(formatted_line, log_type, level)
    
    def _get_color_for_level(self, level: str) -> str:
        """Get color for log level"""
        level_colors = {
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
            "SYSTEM": "cyan",
            "UVICORN": "blue",
            "PRINT": "white"
        }
        return level_colors.get(level, "white")
    
    def _route_to_http(self, line: str, message: str, level: str) -> None:
        """Route HTTP-related logs (requests/responses)"""
        # HTTP logs are INFO level and contain HTTP methods or status codes
        http_indicators = [
            '" 200', '" 201', '" 204', '" 400', '" 401', '" 403', '" 404', '" 500', '" 502', '" 503',
            'POST /', 'GET /', 'PUT /', 'DELETE /', 'PATCH /',
            'HTTP/1.1', 'HTTP/2.0'
        ]
        
        if level == "INFO" and any(indicator in message for indicator in http_indicators):
            try:
                log_http = self.query_one("#log-http", AutoScrollLog)
                log_http.write_line(line)
            except:
                pass
    
    def _route_to_exceptions(self, line: str, level: str) -> None:
        """Route exception logs"""
        if level in ["ERROR", "CRITICAL"]:
            try:
                log_exc = self.query_one("#log-exceptions", AutoScrollLog)
                log_exc.write_line(line)
            except:
                pass
    
    def _route_to_system(self, line: str, log_type: str, message: str) -> None:
        """Route system logs (startup, shutdown, etc)"""
        system_keywords = [
            "Started server", "Waiting for application", "Application startup",
            "Uvicorn running", "Shutting down", "Finished server", "FastAPI process"
        ]
        
        if log_type == "SYSTEM" or any(keyword in message for keyword in system_keywords):
            try:
                log_sys = self.query_one("#log-system", AutoScrollLog)
                log_sys.write_line(line)
            except:
                pass
    
    def _route_to_application(self, line: str, log_type: str, level: str) -> None:
        """Route application logs (your custom UVICORN/PRINT logs)"""
        # Application logs are UVICORN or PRINT type, or custom messages
        if log_type in ["UVICORN", "PRINT"] or (level not in ["ERROR", "CRITICAL"] and log_type not in ["SYSTEM"]):
            # Exclude HTTP logs from application logs
            http_indicators = ['HTTP/1.1', '" 200', '" 400', '" 500']
            if not any(indicator in line for indicator in http_indicators):
                try:
                    log_app = self.query_one("#log-application", AutoScrollLog)
                    log_app.write_line(line)
                except:
                    pass
    
    def clear_all(self) -> None:
        """Clear all log tabs"""
        self.all_logs.clear()
        for log_id in ["log-all", "log-http", "log-exceptions", "log-system", "log-application"]:
            try:
                log_widget = self.query_one(f"#{log_id}", AutoScrollLog)
                log_widget.clear()
            except:
                pass
    
    def load_history(self, logs: List[Dict[str, Any]]) -> None:
        """Load historical logs (e.g., from persistence)"""
        for log_data in logs:
            self.add_log(log_data)