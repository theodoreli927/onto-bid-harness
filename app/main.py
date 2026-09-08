# app/main.py
from fastapi import FastAPI

app = FastAPI(title="Bid Document Analysis Harness")

@app.get("/health")
def health():
    return {"status": "ok"}