from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import Static, DataTable, TabbedContent, TabPane
from textual.containers import Vertical, ScrollableContainer
from textual.reactive import reactive
from typing import List
from rich.text import Text

from ..core.models import EndpointHit, CustomEvent
from .request_inspector import RequestInspector


def log_debug(msg):
    with open("debug.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")


class RequestViewer(Vertical):
    # always_update=True ist wichtig!
    hits: reactive[List[EndpointHit]] = reactive([], always_update=True)
    events: reactive[List[CustomEvent]] = reactive([], always_update=True)
    
    def __init__(self, endpoint: str, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = endpoint
        self._mounted = False
        self._current_viewing_hit_id = None
    
    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Requests", id="requests-tab"):
                yield DataTable(id="requests-table")
            with TabPane("Events", id="events-tab"):
                yield DataTable(id="events-table")
            with TabPane("Details", id="details-tab"):
                yield ScrollableContainer(
                    Static("Select a request to view details", id="details-placeholder"),
                    id="details-scroll"
                )
    
    def on_mount(self) -> None:
        self.styles.border = ("solid", "green")
        
        # TABELLE SETUP
        table = self.query_one("#requests-table", DataTable)
        table.cursor_type = "row"
        
        # WICHTIG: Explizite Keys setzen! Sonst funktioniert update_cell oft nicht richtig.
        table.add_column("Time", key="col_time")
        table.add_column("Method", key="col_method")
        table.add_column("Status", key="col_status")
        table.add_column("Duration", key="col_duration")
        table.add_column("ID", key="col_id")
        
        events_table = self.query_one("#events-table", DataTable)
        events_table.add_columns("Time", "Type", "Level", "Message")
        
        self._mounted = True

    def add_hit(self, hit: EndpointHit) -> None:
        # LOGGING: Was kommt rein?
        # log_debug(f"ADD_HIT aufgerufen für ID={hit.id[:8]} | Pending={hit.pending} | Status={hit.status_code}")

        # 1. Echte Kopie erstellen (WICHTIG!)
        hit_safe = hit.model_copy()
        
        # 2. Index suchen
        existing_index = -1
        for i, h in enumerate(self.hits):
            if h.id == hit_safe.id:
                existing_index = i
                break
        
        # 3. Liste kopieren für Reaktivität
        new_list = self.hits[:]
        
        if existing_index >= 0:
            new_list[existing_index] = hit_safe
            # log_debug(f" -> Update existierender Hit an Index {existing_index}")
        else:
            new_list.insert(0, hit_safe)
            new_list = new_list[:100]
            # log_debug(f" -> Neuer Hit eingefügt")

        # 4. Zuweisen (triggert watch_hits)
        self.hits = new_list
    def add_event(self, event: CustomEvent) -> None:
        self.events = [event] + self.events[:99]

    def watch_hits(self, old_hits: List[EndpointHit], new_hits: List[EndpointHit]) -> None:
        if not self._mounted: return
        
        # log_debug(f"WATCH_HITS getriggert. Anzahl Hits: {len(new_hits)}")
        
        # 1. Tabelle aktualisieren
        self._refresh_table_smart(new_hits)
        
        # 2. Detailansicht aktualisieren
        self._update_inspector_live()
        
        # 3. Erzwinge Neuzeichnen der Tabelle (Sicherheitshalber)
        self.query_one("#requests-table", DataTable).refresh()

    def _refresh_table_smart(self, current_hits: List[EndpointHit]):
        """Refresh table with correct order - newest first."""
        table = self.query_one("#requests-table", DataTable)
        
        # Track which rows exist and need updates vs new rows
        existing_keys = set(table.rows.keys())
        current_keys = {str(hit.id) for hit in current_hits}
        new_keys = current_keys - existing_keys
        
        # If there are new rows, we need to rebuild to maintain order
        # (DataTable.add_row always adds at bottom)
        if new_keys:
            # Remember selected row
            selected_key = None
            if table.cursor_row is not None and table.row_count > 0:
                try:
                    selected_key = table.get_row_at(table.cursor_row)
                except:
                    pass
            
            # Clear and rebuild from scratch in correct order
            table.clear()
            
            for hit in current_hits:  # Already sorted newest-first in self.hits
                row_key = str(hit.id)
                time_str = hit.timestamp.strftime("%H:%M:%S")
                
                if hit.pending:
                    status_render = Text("⏳ PENDING", style="yellow")
                    duration_str = "..."
                else:
                    s_code = hit.status_code
                    if s_code and s_code < 400: style = "green"
                    elif s_code and s_code < 500: style = "yellow"
                    else: style = "red"
                    status_render = Text(str(s_code or "ERR"), style=style)
                    duration_str = f"{hit.duration_ms:.0f}ms" if hit.duration_ms else ""
                
                table.add_row(
                    time_str,
                    hit.method,
                    status_render,
                    duration_str,
                    hit.id[:8],
                    key=row_key
                )
        else:
            # No new rows - just update existing cells
            for hit in current_hits:
                row_key = str(hit.id)
                
                if row_key not in table.rows:
                    continue
                    
                if hit.pending:
                    status_render = Text("⏳ PENDING", style="yellow")
                    duration_str = "..."
                else:
                    s_code = hit.status_code
                    if s_code and s_code < 400: style = "green"
                    elif s_code and s_code < 500: style = "yellow"
                    else: style = "red"
                    status_render = Text(str(s_code or "ERR"), style=style)
                    duration_str = f"{hit.duration_ms:.0f}ms" if hit.duration_ms else ""
                
                table.update_cell(row_key, "col_status", status_render)
                table.update_cell(row_key, "col_duration", duration_str)
    def _update_inspector_live(self):
        """Prüft, ob wir gerade einen Request anschauen, der geupdated wurde."""
        if not self._current_viewing_hit_id:
            return

        # Den aktuellen Hit aus der Liste holen
        # (Wir holen ihn frisch aus self.hits, da dort die neuen Daten liegen)
        current_hit = next((h for h in self.hits if h.id == self._current_viewing_hit_id), None)
        
        if current_hit:
            try:
                inspector = self.query_one(RequestInspector)
                # Wir rufen explizit die Methode auf
                inspector.force_refresh_data(current_hit)
            except:
                pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "requests-table":
            hit_id = event.row_key.value
            hit = next((h for h in self.hits if h.id == hit_id), None)
            if hit:
                self._show_hit_details(hit)

    def _show_hit_details(self, hit: EndpointHit) -> None:
        self._current_viewing_hit_id = hit.id
        
        container = self.query_one("#details-scroll", ScrollableContainer)
        container.remove_children()
        
        inspector = RequestInspector(hit)
        container.mount(inspector)
        
        self.query_one(TabbedContent).active = "details-tab"

    # Events Tabelle Logik (unverändert, nur der Vollständigkeit halber)
    def watch_events(self, old_e, new_e):
        if not self._mounted: return
        table = self.query_one("#events-table", DataTable)
        table.clear()
        for e in new_e:
            table.add_row(
                e.timestamp.strftime("%H:%M:%S"), 
                e.event_type.value, 
                e.level, 
                e.message, 
                key=e.id
            )