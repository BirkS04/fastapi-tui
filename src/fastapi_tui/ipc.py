# app/utils/tui/ipc.py
from multiprocessing.managers import BaseManager
from multiprocessing import Queue
import os

class TUIQueueManager(BaseManager):
    pass

_queue = Queue()

def get_queue():
    return _queue

TUIQueueManager.register('get_queue', callable=get_queue)

def start_manager_server():
    """Startet den Manager im TUI-Prozess"""
    # Wir nutzen Port 0 für automatische Zuweisung
    manager = TUIQueueManager(address=('127.0.0.1', 0), authkey=b'tui_secret')
    manager.start()
    
    # Setze die Env Vars für den aktuellen Prozess (Runner)
    # Diese werden dann an den Subprozess (Uvicorn) vererbt
    os.environ['TUI_IPC_PORT'] = str(manager.address[1])
    os.environ['TUI_IPC_AUTHKEY'] = 'tui_secret'
    
    return manager

def get_queue_client():
    """Client Verbindung für FastAPI"""
    port = os.environ.get('TUI_IPC_PORT')
    authkey = os.environ.get('TUI_IPC_AUTHKEY')
    
    if not port or not authkey:
        # Fallback: Wenn wir lokal ohne TUI Runner testen, aber .env Werte haben
        # (Nur nutzen wenn du wirklich manuell testen willst, sonst besser None)
        return None
        
    class QueueClient(BaseManager):
        pass
    
    QueueClient.register('get_queue')
    
    try:
        manager = QueueClient(address=('127.0.0.1', int(port)), authkey=authkey.encode('utf-8'))
        manager.connect()
        return manager.get_queue()
    except Exception as e:
        print(f"⚠️ TUI IPC Connection failed: {e}")
        return None