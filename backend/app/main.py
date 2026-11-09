"""StormSense AI - FastAPI application entry point.  Run:  uvicorn app.main:app --reload --port 8000"""
import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .db import database as db

logging.basicConfig(level=os.environ.get("STORMSENSE_LOG_LEVEL", "INFO"),
                    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}')
log = logging.getLogger("stormsense")

app = FastAPI(title="StormSense AI", version="1.0.0",
              description="Historical extreme-weather intelligence: hierarchical and density-based clustering of NOAA Storm Events (SIH26078).")

origins = [o.strip() for o in os.environ.get("STORMSENSE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    db.init_db()
    log.info("database ready")


@app.middleware("http")
async def access_log(request: Request, call_next):
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error on %s %s", request.method, request.url.path)  # never logs bodies or tokens
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, (time.perf_counter() - t0) * 1000)
    return response


app.include_router(router)
