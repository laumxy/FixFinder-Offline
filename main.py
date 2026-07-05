import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import pipeline, router
from app.api.v2_routes import router as v2_router
from app.core.bootstrap import ensure_runtime_assets
from fixfinder_engine.config import settings


def _warm_up_in_background() -> None:
    """
    Load the FAISS index + embedding model in a background thread so the
    server can accept requests immediately.  The first request that arrives
    before warm-up completes will still work — it just pays the cold-start
    cost once.
    """
    try:
        ensure_runtime_assets(pipeline.vector_search)
        pipeline.vector_search.warm_up()
    except Exception as exc:  # noqa: BLE001
        # Warm-up failure is non-fatal — the pipeline degrades gracefully
        print(f"[bootstrap] warm-up error (non-fatal): {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start warm-up in background so the server is immediately available.
    t = threading.Thread(target=_warm_up_in_background, daemon=True, name="bootstrap-warmup")
    t.start()
    app.state.pipeline = pipeline
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Offline-first AI troubleshooting engine for real-world repair guidance.",
        lifespan=lifespan,
    )
    app.include_router(router)
    app.include_router(v2_router)
    return app


app = create_app()
