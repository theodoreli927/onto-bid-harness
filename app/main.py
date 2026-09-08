# app/main.py
from fastapi import FastAPI
from app.store.db import init_db
from app.harness import models  # noqa: F401 — import registers tables with Base.metadata

app = FastAPI(title="Bid Document Analysis Harness")


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/health")
def health():
    return {"status": "ok"}