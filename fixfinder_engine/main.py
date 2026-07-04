from main import app, create_app


if __name__ == "__main__":
    import uvicorn
    from fixfinder_engine.config import settings

    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.reload)
