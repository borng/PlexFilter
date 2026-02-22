from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .routes.library import router as library_router
from .routes.profiles import router as profiles_router
from .routes.sync import router as sync_router
from .routes.categories import router as categories_router
from .routes.generate import router as generate_router

app = FastAPI(title="PlexFilter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(library_router)
app.include_router(profiles_router)
app.include_router(sync_router)
app.include_router(categories_router)
app.include_router(generate_router)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
