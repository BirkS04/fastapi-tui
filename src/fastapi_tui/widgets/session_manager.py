from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import Static, DataTable, Label
from textual.containers import Vertical
from textual.message import Message
from ..persistence import get_persistence

class SessionManager(Static):
    """
    Widget zur Verwaltung und Auswahl von gespeicherten Sessions.
    """
    
    class SessionSelected(Message):
        """Nachricht, wenn eine Session ausgewählt wurde."""
        def __init__(self, session_id: str):
            self.session_id = session_id
            super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("💾 Saved Sessions", classes="section-title")
            yield DataTable(id="session-table", cursor_type="row")

    def on_mount(self) -> None:
        """Lädt die Sessions beim Start."""
        self.load_sessions()

    def load_sessions(self) -> None:
        table = self.query_one("#session-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Start Time", "ID", "Status")
        
        persistence = get_persistence()
        sessions = persistence.get_sessions()
        current_session_id = persistence.current_session_id
        
        # Sessions iterieren
        for session in sessions:
            s_id = session["id"]
            # Timestamp formatieren
            ts_raw = session["start_time"]
            if isinstance(ts_raw, str):
                try:
                    ts = datetime.fromisoformat(ts_raw)
                    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    ts_str = str(ts_raw)
            else:
                ts_str = ts_raw.strftime("%Y-%m-%d %H:%M:%S")
            
            # Status markieren
            status = session.get("name", "")
            if s_id == current_session_id:
                status = f"🟢 CURRENT ({status})"
                # Wir markieren die aktuelle Session visuell
                ts_str = f"[bold green]{ts_str}[/]"
                s_id_display = f"[bold green]{s_id}[/]"
            else:
                s_id_display = s_id
            
            table.add_row(ts_str, s_id_display, status, key=s_id)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handler für Klick auf eine Zeile."""
        if event.row_key:
            session_id = event.row_key.value
            self.post_message(self.SessionSelected(session_id))