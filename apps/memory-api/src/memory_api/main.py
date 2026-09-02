from fastapi import FastAPI

from memory_api.routers import api_keys, auth, health, memories

app = FastAPI(title="Memoria Memory API")
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(memories.router)
