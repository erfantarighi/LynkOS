import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.ddns import runner as ddns_runner
from app.metrics import collector as metrics_collector
from app.routers import adblock, auth, clients, ddns, fail2ban, interfaces, metrics, pppoe, routes, speedtest, ssh, system, vlan, wifi, wireguard
from app.routers import snapshot as snapshot_router
from app.snapshot import apply_all

settings = get_settings()
log = logging.getLogger("lynkos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.mock_mode:
        try:
            results = await apply_all()
            log.info("snapshot applied on startup: %s", results)
        except Exception:
            log.exception("snapshot apply on startup failed")
        try:
            await ddns_runner.start()
        except Exception:
            log.exception("ddns runner failed to start")
    try:
        await metrics_collector.start()
    except Exception:
        log.exception("metrics collector failed to start")
    yield
    await ddns_runner.stop()
    await metrics_collector.stop()


app = FastAPI(
    title="LynkOS",
    description="Manage a Raspberry Pi as a WiFi router (NetworkManager + PPPoE).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(wifi.router)
app.include_router(pppoe.router)
app.include_router(interfaces.router)
app.include_router(vlan.router)
app.include_router(clients.router)
app.include_router(routes.router)
app.include_router(snapshot_router.router)
app.include_router(ddns.router)
app.include_router(wireguard.router)
app.include_router(speedtest.router)
app.include_router(fail2ban.router)
app.include_router(adblock.router)
app.include_router(ssh.router)
app.include_router(metrics.router)
app.include_router(system.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the built frontend when it's available (production). In dev, Vite runs
# separately on :5173 and proxies /api to this server.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        # Let React Router handle client routes; always serve index.html for non-/api paths.
        target = FRONTEND_DIST / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
