from dotenv import load_dotenv
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Deine Router
from app.utils.classes import RatingResponse, Rating
from app.routers.agents5 import router as agents5_router
from app.routers.tools import router as tools_router
from app.routers.flow_tools import router as flow_tools_router
from app.routers.flow_edit_tools import router as flow_edit_tools_router
from app.routers.crawl import router as crawl_router

# TUI Imports
from fastapi_tui import with_tui, TUIConfig, create_tui_app
from fastapi_tui.exception_handler_utils import handle_exception_with_tui

load_dotenv()

version = os.getenv("API_VERSION", "v1")

# --- 1. APP ERSTELLEN (Ganz normal) ---
app = FastAPI()



# --- 3. MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. EXCEPTION HANDLER ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return handle_exception_with_tui(
        request, 
        exc,
        error_message="Internal Server Error Critical"
    )

# --- 5. ROUTER ---
app.include_router(tools_router, prefix=f"/api/{version}/tools", tags=["tools"])
app.include_router(flow_tools_router, prefix=f"/api/{version}", tags=["flow-tools"])
app.include_router(flow_edit_tools_router, prefix=f"/api/{version}", tags=["flow-edit-tools"])
app.include_router(crawl_router, prefix=f"/api/{version}", tags=["crawl"])
app.include_router(agents5_router, prefix=f"/api/{version}/agents", tags=["agents"])

# --- 2. TUI KONFIGURIEREN ---
# Das muss hier stehen, damit die Middleware geladen wird
app = create_tui_app(app)

# --- 6. ENTRY POINT ---
if __name__ == "__main__":
    # Config erstellen
    config = TUIConfig(
        enable_persistence=False,
        
        # NEU: Endpoints filtern
        exclude_paths={
            "/health",
            "/metrics", 
            "/docs", 
            "/redoc", 
            "/openapi.json"
        },
        exclude_methods={
        }
    )
    
    # Starten
    with_tui(
        app=app,
        app_module="app.main:app",
        config=config,
        host="127.0.0.1",
        port=8000
    )