"""
Main Application Entrypoint
============================
FastAPI Application serving Role-Based APIs, ACID Transaction Handlers,
and the White-and-Green Bubble UI presentation layer.
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from app.routes.auth_routes import router as auth_router
from app.routes.waiter_routes import router as waiter_router
from app.routes.chef_routes import router as chef_router
from app.routes.kitchen_routes import router as kitchen_router
from app.routes.manager_routes import router as manager_router

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="Role-Based Relational Database Architecture for Modern Restaurant Management",
    description="Course Context: Database System Design | 3NF Relational Normalization, Ferraiolo-Kuhn RBAC & Jim Gray ACID Transactions",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(waiter_router)
app.include_router(chef_router)
app.include_router(kitchen_router)
app.include_router(manager_router)

# Mount Static Files
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
def startup_event():
    """Ensure database schema, views, and seed data are initialized on launch."""
    init_db()
    print("[Server] Relational Database Initialized & Ready.")


@app.get("/")
def serve_index():
    """Serves the White-and-Green Bubble UI single page application."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "Restaurant Management System API is running. UI is initializing..."}


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "system": "Restaurant Relational DBMS",
        "normalization": "3NF",
        "rbac_model": "Ferraiolo & Kuhn",
        "concurrency": "Jim Gray ACID"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
