import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Set, Dict, Any
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
    
    def to_json_payload(self) -> str:
        """
        Serialisiert die Config zu einem JSON-String für die Übergabe an Subprozesse.
        Wandelt Sets in Listen und Enums in Values um.
        """
        data = asdict(self)
        
        # Manuelle Konvertierung für nicht-JSON-serialisierbare Typen
        # Sets zu Listen
        data["exclude_paths"] = list(self.exclude_paths)
        data["exclude_methods"] = list(self.exclude_methods)
        data["mask_headers"] = list(self.mask_headers)
        data["mask_body_fields"] = list(self.mask_body_fields)
        
        # Enum zu String
        data["log_level"] = self.log_level.value
        
        return json.dumps(data)

    @classmethod
    def from_json_payload(cls, payload: str) -> "TUIConfig":
        """
        Erstellt Config aus dem JSON-Payload des Parent-Prozesses.
        """
        data = json.loads(payload)
        
        # Rückkonvertierung der Typen
        # Listen zu Sets
        if "exclude_paths" in data: data["exclude_paths"] = set(data["exclude_paths"])
        if "exclude_methods" in data: data["exclude_methods"] = set(data["exclude_methods"])
        if "mask_headers" in data: data["mask_headers"] = set(data["mask_headers"])
        if "mask_body_fields" in data: data["mask_body_fields"] = set(data["mask_body_fields"])
        
        # String zu Enum
        if "log_level" in data: data["log_level"] = LogLevel(data["log_level"])
        
        return cls(**data)

    @classmethod
    def from_env(cls) -> "TUIConfig":
        """Create config from environment variables (Fallback)"""
        return cls(
            host=os.getenv("TUI_HOST", "0.0.0.0"),
            port=int(os.getenv("TUI_PORT", "8000")),
            reload=os.getenv("TUI_RELOAD", "").lower() in ("1", "true", "yes"),
            enable_exceptions=os.getenv("TUI_EXCEPTIONS", "1").lower() in ("1", "true", "yes"),
            enable_request_logging=os.getenv("TUI_REQUEST_LOGGING", "1").lower() in ("1", "true", "yes"),
            log_level=LogLevel(os.getenv("TUI_LOG_LEVEL", "info").lower()),
            db_path=os.getenv("TUI_DB_PATH", "tui_events.db"),
            enable_persistence=os.getenv("TUI_ENABLE_PERSISTENCE", "1").lower() in ("1", "true", "yes"),
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
    """
    Get the global TUI config.
    Priorität:
    1. Bereits gesetztes globales Objekt (_config)
    2. JSON Payload vom Parent-Prozess (TUI_CONFIG_PAYLOAD)
    3. CLI/Environment Defaults
    """
    global _config
    if _config is None:
        # Check for payload from runner
        payload = os.environ.get("TUI_CONFIG_PAYLOAD")
        if payload:
            try:
                _config = TUIConfig.from_json_payload(payload)
            except Exception as e:
                print(f"[WARN] Failed to load config from payload: {e}")
                _config = TUIConfig.from_cli()
        else:
            _config = TUIConfig.from_cli()
            
    return _config


def set_config(config: TUIConfig) -> None:
    """Set the global TUI config"""
    global _config
    _config = config