# app/main.py
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.store.db import init_db
from app.harness import models  # noqa: F401
from app.api import projects, documents, tasks
from app.worker import worker_loop
from fastapi.responses import RedirectResponse

app = FastAPI(title="Bid Document Analysis Harness")

app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(tasks.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def on_startup():
    await init_db()
    asyncio.create_task(worker_loop())


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return RedirectResponse(url="/static/viewer.html")
