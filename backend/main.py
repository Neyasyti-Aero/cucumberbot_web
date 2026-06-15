from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from src.frameworks.ros.rosbridge_client import get_rosbridge_client
from src.interface_adapters.controllers.auth_router import router as auth_router
from src.interface_adapters.controllers.maps_router import router as maps_router
from src.interface_adapters.controllers.qr_router import router as qr_router
from src.interface_adapters.controllers.robot_router import router as robot_router
from src.interface_adapters.controllers.terminal_router import router as terminal_router
from src.interface_adapters.controllers.users_router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = get_rosbridge_client()
    await client.connect()
    yield
    await client.disconnect()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(robot_router, prefix="/api/v1/robot", tags=["robot"])
app.include_router(maps_router, prefix="/api/v1/maps", tags=["maps"])
app.include_router(qr_router, prefix="/api/v1/qr", tags=["qr"])
app.include_router(terminal_router, prefix="/api/v1/terminal", tags=["terminal"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
