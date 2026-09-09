# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.store.db import init_db
from app.harness import models  # noqa: F401
from app.api import projects, documents, tasks

app = FastAPI(title="Bid Document Analysis Harness")

app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(tasks.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
