from fastapi import FastAPI
from src.api.routes.slack import router as slack_router
from src.core.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Slack AI Data Bot",
    description="Natural language to SQL bot for Slack",
    version="1.0.0"
)

app.include_router(slack_router, prefix="/slack", tags=["slack"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    logger.info("Slack AI Data Bot starting up...")