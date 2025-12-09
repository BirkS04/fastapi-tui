"""
TUI Configuration

Central configuration for the TUI system.
All settings can be customized via environment variables or programmatically.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Set
from enum import Enum


class LogLevel(str, Enum):
    """Log levels for TUI output"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TUIConfig:
    """
    Configuration for the TUI system.
    
    Usage:
        from fastapi_tui import TUIConfig, with_tui
        
        config = TUIConfig(
            port=8080,
            enable_exceptions=True,
            log_level=LogLevel.DEBUG
        )
        with_tui(app, config=config)
    """
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Hot-reload settings
    reload: bool = False
    reload_dirs: List[str] = field(default_factory=lambda: ["app"])
    
    # Feature toggles
    enable_exceptions: bool = True
    enable_request_logging: bool = True
    enable_response_body: bool = True
    enable_runtime_logs: bool = True
    enable_stats: bool = True
    enable_persistence: bool = True
    
    # Logging settings
    log_level: LogLevel = LogLevel.INFO
    log_to_file: bool = False
    log_file_path: str = "tui.log"
    
    # UI settings  
    show_sidebar: bool = True
    show_stats_panel: bool = True
    max_hits_display: int = 100
    max_log_lines: int = 1000
    
    # Request filtering
    exclude_paths: Set[str] = field(default_factory=lambda: {
        "/health",
        "/healthz", 
        "/ready",
        "/metrics",
        "/favicon.ico"
    })
    exclude_methods: Set[str] = field(default_factory=set)
    
    # Sensitive data masking
    mask_headers: Set[str] = field(default_factory=lambda: {
        "authorization",
        "x-api-key",
        "cookie",
        "set-cookie"
    })
    mask_body_fields: Set[str] = field(default_factory=lambda: {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token"
    })
    
    # Persistence settings
    db_path: str = "tui_events.db"
    
    @classmethod
    def from_env(cls) -> "TUIConfig":
        """Create config from environment variables"""
        return cls(
            host=os.getenv("TUI_HOST", "0.0.0.0"),
            port=int(os.getenv("TUI_PORT", "8000")),
            reload=os.getenv("TUI_RELOAD", "").lower() in ("1", "true", "yes"),
            enable_exceptions=os.getenv("TUI_EXCEPTIONS", "1").lower() in ("1", "true", "yes"),
            enable_request_logging=os.getenv("TUI_REQUEST_LOGGING", "1").lower() in ("1", "true", "yes"),
            log_level=LogLevel(os.getenv("TUI_LOG_LEVEL", "info").lower()),
            db_path=os.getenv("TUI_DB_PATH", "tui_events.db"),
        )
    
    @classmethod
    def from_cli(cls) -> "TUIConfig":
        """Create config from CLI arguments"""
        import sys
        
        config = cls.from_env()
        
        # Parse CLI flags
        if "--reload" in sys.argv or "--dev" in sys.argv:
            config.reload = True
        
        # Parse --port=XXXX
        for arg in sys.argv:
            if arg.startswith("--port="):
                config.port = int(arg.split("=")[1])
            elif arg.startswith("--host="):
                config.host = arg.split("=")[1]
        
        return config
    
    def should_log_request(self, path: str, method: str) -> bool:
        """Check if a request should be logged"""
        if path in self.exclude_paths:
            return False
        if method.upper() in self.exclude_methods:
            return False
        return self.enable_request_logging
    
    def mask_value(self, key: str, value: str) -> str:
        """Mask sensitive values"""
        key_lower = key.lower()
        if key_lower in self.mask_headers or key_lower in self.mask_body_fields:
            return "***"
        return value


# Global config instance
_config: Optional[TUIConfig] = None


def get_config() -> TUIConfig:
    """Get the global TUI config"""
    global _config
    if _config is None:
        _config = TUIConfig.from_cli()
    return _config


def set_config(config: TUIConfig) -> None:
    """Set the global TUI config"""
    global _config
    _config = config
