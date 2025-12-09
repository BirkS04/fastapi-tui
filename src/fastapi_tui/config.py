import os
import sys
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Set
from enum import Enum

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class TUIConfig:
    # ... (Deine Felder bleiben gleich) ...
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    reload_dirs: List[str] = field(default_factory=lambda: ["app"])
    
    enable_exceptions: bool = True
    enable_request_logging: bool = True
    enable_response_body: bool = True
    enable_runtime_logs: bool = True
    enable_stats: bool = True
    enable_persistence: bool = True
    
    log_level: LogLevel = LogLevel.INFO
    log_to_file: bool = False
    log_file_path: str = "tui.log"
    
    show_sidebar: bool = True
    show_stats_panel: bool = True
    max_hits_display: int = 100
    max_log_lines: int = 1000
    
    exclude_paths: Set[str] = field(default_factory=lambda: {
        
    })
    exclude_methods: Set[str] = field(default_factory=set)
    
    mask_headers: Set[str] = field(default_factory=lambda: {
        "authorization", "x-api-key", "cookie", "set-cookie"
    })
    mask_body_fields: Set[str] = field(default_factory=lambda: {
        "password", "secret", "token", "api_key", "apikey", "access_token", "refresh_token"
    })
    
    db_path: str = "tui_events.db"
    
    def override_from_cli(self) -> None:
        """
        Überschreibt Config-Werte mit CLI-Argumenten.
        CLI hat immer Vorrang vor Code-Config!
        """
        # 1. Reload Flag
        if "--reload" in sys.argv:
            self.reload = True
            
        # 2. Port Parsing (--port=8000 oder --port 8000)
        # Wir machen hier ein einfaches Parsing, um argparse Konflikte zu vermeiden
        for i, arg in enumerate(sys.argv):
            if arg.startswith("--port="):
                try:
                    self.port = int(arg.split("=")[1])
                except ValueError: pass
            elif arg == "--port" and i + 1 < len(sys.argv):
                try:
                    self.port = int(sys.argv[i+1])
                except ValueError: pass
                
            # 3. Host Parsing
            if arg.startswith("--host="):
                self.host = arg.split("=")[1]
            elif arg == "--host" and i + 1 < len(sys.argv):
                self.host = sys.argv[i+1]

    def to_json_payload(self) -> str:
        data = asdict(self)
        data["exclude_paths"] = list(self.exclude_paths)
        data["exclude_methods"] = list(self.exclude_methods)
        data["mask_headers"] = list(self.mask_headers)
        data["mask_body_fields"] = list(self.mask_body_fields)
        data["log_level"] = self.log_level.value
        return json.dumps(data)

    @classmethod
    def from_json_payload(cls, payload: str) -> "TUIConfig":
        data = json.loads(payload)
        if "exclude_paths" in data: data["exclude_paths"] = set(data["exclude_paths"])
        if "exclude_methods" in data: data["exclude_methods"] = set(data["exclude_methods"])
        if "mask_headers" in data: data["mask_headers"] = set(data["mask_headers"])
        if "mask_body_fields" in data: data["mask_body_fields"] = set(data["mask_body_fields"])
        if "log_level" in data: data["log_level"] = LogLevel(data["log_level"])
        return cls(**data)

    @classmethod
    def from_env(cls) -> "TUIConfig":
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
        config = cls.from_env()
        config.override_from_cli() # Hier auch direkt anwenden
        return config

# ... (Rest der Datei: get_config, set_config bleiben gleich) ...
_config: Optional[TUIConfig] = None

def get_config() -> TUIConfig:
    global _config
    if _config is None:
        payload = os.environ.get("TUI_CONFIG_PAYLOAD")
        if payload:
            try:
                _config = TUIConfig.from_json_payload(payload)
            except Exception:
                _config = TUIConfig.from_cli()
        else:
            _config = TUIConfig.from_cli()
    return _config

def set_config(config: TUIConfig) -> None:
    global _config
    _config = config