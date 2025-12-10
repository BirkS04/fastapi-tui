import os
import sys
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Set, Dict, Any
from enum import Enum

class LogLevel(str, Enum):
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
    # DEFAULT: Alles an, außer man schaltet es explizit aus
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
    # Standardmäßig filtern wir nur technische Health-Checks.
    # Alles andere wird geloggt.
    exclude_paths: Set[str] = field(default_factory=lambda: {})
    
    exclude_methods: Set[str] = field(default_factory=set)
    
    # Endpoint Display Customization
    # Prefixe die aus der Anzeige entfernt werden sollen
    strip_prefixes: List[str] = field(default_factory=list)
    
    # String-Replacements für Endpoint-Namen
    # Format: {"original": "replacement"}
    endpoint_replacements: Dict[str, str] = field(default_factory=dict)
    
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

    # --- LOGIC METHODS ---

    def should_log_request(self, path: str, method: str) -> bool:
        """
        Entscheidet, ob ein Request geloggt werden soll.
        Standardmäßig JA, außer er ist explizit ausgeschlossen.
        """
        # 1. Globaler Schalter
        if not self.enable_request_logging:
            return False
            
        # 2. Pfad-Ausschluss (exakter Match)
        if path in self.exclude_paths:
            return False
            
        # 3. Methoden-Ausschluss
        if method.upper() in self.exclude_methods:
            return False
            
        return True

    def format_endpoint_for_display(self, path: str) -> str:
        """
        Formatiert einen Endpoint-Path für die Anzeige in der UI.
        
        1. Entfernt konfigurierte Prefixe
        2. Führt String-Replacements durch
        
        Beispiel:
            path = "/api/v1/tools/zusammenfassung"
            strip_prefixes = ["/api/v1"]
            endpoint_replacements = {"zusammenfassung": "zsm"}
            → Result: "/tools/zsm"
        """
        formatted = path
        
        # 1. Strip Prefixes (längste zuerst, um /api/v1 vor /api zu matchen)
        for prefix in sorted(self.strip_prefixes, key=len, reverse=True):
            if formatted.startswith(prefix):
                formatted = formatted[len(prefix):]
                break  # Nur ersten Match anwenden
        
        # 2. Apply Replacements
        for original, replacement in self.endpoint_replacements.items():
            formatted = formatted.replace(original, replacement)
        
        # Stelle sicher dass der Path mit / beginnt
        if not formatted.startswith("/"):
            formatted = "/" + formatted
            
        return formatted

    def scrub_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Maskiert Header basierend auf der Config."""
        scrubbed = {}
        for key, value in headers.items():
            if key.lower() in self.mask_headers:
                scrubbed[key] = "***"
            else:
                scrubbed[key] = value
        return scrubbed

    def scrub_data(self, data: Any) -> Any:
        """
        Rekursive Funktion zum Maskieren von sensiblen Feldern in JSON-Daten.
        """
        if isinstance(data, dict):
            return {
                k: "***" if k.lower() in self.mask_body_fields else self.scrub_data(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self.scrub_data(item) for item in data]
        else:
            return data
    
    # --- SERIALIZATION METHODS ---

    def override_from_cli(self) -> None:
        """CLI Argumente haben Vorrang."""
        if "--reload" in sys.argv:
            self.reload = True
            
        for i, arg in enumerate(sys.argv):
            if arg.startswith("--port="):
                try:
                    self.port = int(arg.split("=")[1])
                except ValueError: pass
            elif arg == "--port" and i + 1 < len(sys.argv):
                try:
                    self.port = int(sys.argv[i+1])
                except ValueError: pass
            
            if arg.startswith("--host="):
                self.host = arg.split("=")[1]
            elif arg == "--host" and i + 1 < len(sys.argv):
                self.host = sys.argv[i+1]

    def to_json_payload(self) -> str:
        data = asdict(self)
        # Sets zu Listen konvertieren für JSON
        data["exclude_paths"] = list(self.exclude_paths)
        data["exclude_methods"] = list(self.exclude_methods)
        data["mask_headers"] = list(self.mask_headers)
        data["mask_body_fields"] = list(self.mask_body_fields)
        data["log_level"] = self.log_level.value
        return json.dumps(data)

    @classmethod
    def from_json_payload(cls, payload: str) -> "TUIConfig":
        data = json.loads(payload)
        # Listen zurück zu Sets
        if "exclude_paths" in data: data["exclude_paths"] = set(data["exclude_paths"])
        if "exclude_methods" in data: data["exclude_methods"] = set(data["exclude_methods"])
        if "mask_headers" in data: data["mask_headers"] = set(data["mask_headers"])
        if "mask_body_fields" in data: data["mask_body_fields"] = set(data["mask_body_fields"])
        if "log_level" in data: data["log_level"] = LogLevel(data["log_level"])
        return cls(**data)

    @classmethod
    def from_env(cls) -> "TUIConfig":
        # Parse strip_prefixes from env (comma-separated)
        strip_prefixes_str = os.getenv("TUI_STRIP_PREFIXES", "")
        strip_prefixes = [p.strip() for p in strip_prefixes_str.split(",") if p.strip()]
        
        # Parse endpoint_replacements from env (JSON string)
        replacements_str = os.getenv("TUI_ENDPOINT_REPLACEMENTS", "{}")
        try:
            endpoint_replacements = json.loads(replacements_str)
        except json.JSONDecodeError:
            endpoint_replacements = {}
        
        return cls(
            host=os.getenv("TUI_HOST", "0.0.0.0"),
            port=int(os.getenv("TUI_PORT", "8000")),
            reload=os.getenv("TUI_RELOAD", "").lower() in ("1", "true", "yes"),
            enable_exceptions=os.getenv("TUI_EXCEPTIONS", "1").lower() in ("1", "true", "yes"),
            enable_request_logging=os.getenv("TUI_REQUEST_LOGGING", "1").lower() in ("1", "true", "yes"),
            log_level=LogLevel(os.getenv("TUI_LOG_LEVEL", "info").lower()),
            db_path=os.getenv("TUI_DB_PATH", "tui_events.db"),
            enable_persistence=os.getenv("TUI_ENABLE_PERSISTENCE", "1").lower() in ("1", "true", "yes"),
            strip_prefixes=strip_prefixes,
            endpoint_replacements=endpoint_replacements,
        )
    
    @classmethod
    def from_cli(cls) -> "TUIConfig":
        config = cls.from_env()
        config.override_from_cli()
        return config


# Global config instance
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