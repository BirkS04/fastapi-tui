"""
Endpoint-Liste Widget - Sidebar mit allen getrackten Endpoints mit Reactive State
"""

from textual.app import ComposeResult
from textual.widgets import Static, ListView, ListItem, Label
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.message import Message
from typing import Dict, List
from rich.text import Text


class EndpointListItem(ListItem):
    """Ein einzelner Endpoint in der Liste"""
    
    def __init__(self, endpoint: str, display_endpoint: str, method: str, hit_count: int = 0):
        super().__init__()
        self.endpoint = endpoint  # Original path für interne Logik
        self.display_endpoint = display_endpoint  # Formatierter path für Anzeige
        self.method = method
        self.hit_count = hit_count
    
    def compose(self) -> ComposeResult:
        method_colors = {
            "GET": "green",
            "POST": "blue",
            "PUT": "yellow",
            "DELETE": "red",
            "PATCH": "magenta",
        }
        
        method_color = method_colors.get(self.method, "white")
        
        label_text = Text()
        label_text.append(f"{self.method:6}", style=f"bold {method_color}")
        label_text.append(" ")
        label_text.append(self.display_endpoint, style="cyan")
        label_text.append(f" ({self.hit_count})", style="dim")
        
        yield Label(label_text)


class EndpointList(Vertical):
    """Sidebar mit Liste aller Endpoints"""
    
    # Reactive Properties - Triggern automatisch watch_* Methoden
    endpoints: reactive[Dict[str, Dict]] = reactive({}, always_update=True)
    selected_endpoint: reactive[str] = reactive("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "📡 Endpoints"
        self._mounted = False
        self._config = None
    
    def compose(self) -> ComposeResult:
        yield ListView(id="endpoint-listview")
    
    def on_mount(self) -> None:
        """Widget wurde gemountet"""
        self.styles.border = ("solid", "blue")
        self._mounted = True
        
        # Config laden
        try:
            from ..config import get_config
            self._config = get_config()
        except ImportError:
            self._config = None
        
        # Initial refresh falls schon Daten vorhanden
        if self.endpoints:
            self._refresh_list()
    
    # ============================================================================
    # REACTIVE WATCHER - Wird automatisch bei Änderungen aufgerufen
    # ============================================================================
    
    def watch_endpoints(self, old_endpoints: Dict[str, Dict], new_endpoints: Dict[str, Dict]) -> None:
        """
        Wird automatisch aufgerufen wenn self.endpoints sich ändert.
        Triggert automatisches UI-Update!
        """
        if self._mounted:
            self._refresh_list()
            if new_endpoints:
                total_hits = sum(e["hit_count"] for e in new_endpoints.values())
                self.log(f"Endpoints updated: {len(new_endpoints)} endpoints, {total_hits} total hits")
    
    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    def add_endpoint(self, endpoint: str, method: str = "GET") -> None:
        """
        Fügt einen neuen Endpoint zur Liste hinzu oder erhöht den Hit-Count.
        Das Update auf self.endpoints triggert automatisch watch_endpoints()!
        """
        # Erstelle neue Dict-Instanz damit Textual die Änderung erkennt
        current_endpoints = dict(self.endpoints)
        
        if endpoint not in current_endpoints:
            current_endpoints[endpoint] = {
                "method": method,
                "hit_count": 0
            }
        
        current_endpoints[endpoint]["hit_count"] += 1
        self.endpoints = current_endpoints  # ← Triggert watch_endpoints()
    
    def clear(self) -> None:
        """Leert die Liste komplett."""
        # Das Setzen auf ein leeres Dict triggert watch_endpoints,
        # welches dann _refresh_list aufruft und die ListView leert.
        self.endpoints = {}
    
    # ============================================================================
    # INTERNAL UI UPDATES
    # ============================================================================
    
    def _format_endpoint(self, endpoint: str) -> str:
        """Formatiert einen Endpoint für die Anzeige gemäß Config."""
        if self._config:
            return self._config.format_endpoint_for_display(endpoint)
        return endpoint
    
    def _refresh_list(self) -> None:
        """Aktualisiert die ListView"""
        if not self._mounted:
            return
            
        try:
            listview = self.query_one("#endpoint-listview", ListView)
            listview.clear()
            
            # Sortiere Endpoints nach Hit-Count
            sorted_endpoints = sorted(
                self.endpoints.items(),
                key=lambda x: x[1]["hit_count"],
                reverse=True
            )
            
            for endpoint, data in sorted_endpoints:
                # Formatiere den Endpoint für die Anzeige
                display_endpoint = self._format_endpoint(endpoint)
                
                item = EndpointListItem(
                    endpoint=endpoint,  # Original für interne Logik
                    display_endpoint=display_endpoint,  # Formatiert für Anzeige
                    method=data["method"],
                    hit_count=data["hit_count"]
                )
                listview.append(item)
        except Exception as e:
            self.log(f"Error refreshing endpoint list: {e}")
    
    # ============================================================================
    # EVENT HANDLERS
    # ============================================================================
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Endpoint wurde ausgewählt"""
        if isinstance(event.item, EndpointListItem):
            # Verwende den ORIGINAL endpoint für die Selektion, nicht den formatierten
            self.selected_endpoint = event.item.endpoint
            # Post message für Parent
            self.post_message(self.EndpointSelected(event.item.endpoint))
    
    class EndpointSelected(Message):
        """Message wenn Endpoint ausgewählt wurde"""
        def __init__(self, endpoint: str):
            super().__init__()
            self.endpoint = endpoint