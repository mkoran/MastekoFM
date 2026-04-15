"""MastekoFM API — FastAPI application."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import assumptions, auth, dag, datasources, health, projects, spreadsheets, templates

app = FastAPI(
    title="MastekoFM API",
    version=os.getenv("VERSION", "0.0.0"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://dev-masteko-fm.web.app",
        "https://masteko-fm.web.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(assumptions.router)
app.include_router(datasources.router)
app.include_router(templates.router)
app.include_router(spreadsheets.router)
app.include_router(dag.router)
