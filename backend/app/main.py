from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import generate, export, health
from app.config import settings
import logging

logger = logging.getLogger("uvicorn")

app = FastAPI(title="Universal Question Generator", version="1.0.0")

@app.on_event("startup")
def startup_event():
    import os
    logger.info("Checking environment variables in os.environ (presence only):")
    for key in sorted(os.environ.keys()):
        if key.startswith("AZURE_OPENAI_"):
            logger.info(f"  {key} in os.environ: {bool(os.environ[key])}")
            
    logger.info("Checking settings values from Pydantic settings object:")
    logger.info(f"  settings.azure_openai_api_key configured: {bool(settings.azure_openai_api_key)}")
    logger.info(f"  settings.azure_openai_endpoint configured: {bool(settings.azure_openai_endpoint)}")
    logger.info(f"  settings.azure_openai_deployment_name: {settings.azure_openai_deployment_name}")
    logger.info(f"  settings.azure_openai_api_version: {settings.azure_openai_api_version}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(generate.router)
app.include_router(export.router)

