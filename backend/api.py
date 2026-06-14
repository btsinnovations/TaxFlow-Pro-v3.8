from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import upload, clients, accounts, audit, tax, ml, export, tests, dashboard, auth

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TaxFlow Pro", version="3.7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(clients.router)
app.include_router(upload.router)
app.include_router(export.router)
app.include_router(dashboard.router)
app.include_router(tax.router)
app.include_router(ml.router)
app.include_router(audit.router)
app.include_router(tests.router)

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.7.0", "pipeline": "TaxFlow Pro"}
