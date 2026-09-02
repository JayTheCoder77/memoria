from fastapi import FastAPI

from memory_api.routers import health, memories

app = FastAPI(title="Memoria Memory API")
app.include_router(health.router)
app.include_router(memories.router)
