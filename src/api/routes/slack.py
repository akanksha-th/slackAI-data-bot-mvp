import hashlib
import hmac
import time
import json
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from src.core.config import get_settings, Settings
from src.core.logging import get_logger
from src.services.llm_service import run_agent
from src.services.cache import CacheService
from src.services.slack_client import post_message, upload_csv, post_ephemeral_ack
from src.utils.formatter import format_results_for_slack, format_error_for_slack
from src.utils.csv_generator import generate_csv

router = APIRouter()
logger = get_logger(__name__)
cache = CacheService()


# --- Slack signature verification ---
def verify_slack_signature(request_body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    if abs(time.time() - float(timestamp)) > 300:
        return False  # replay attack protection
    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


async def slack_auth(request: Request, settings: Settings = Depends(get_settings)):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not verify_slack_signature(body, timestamp, signature, settings.SLACK_SIGNING_SECRET):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    return body


# --- Background task ---
def process_query(question: str, channel: str, response_url: str):
    logger.info(f"Processing question: '{question}' for channel: {channel}")
    try:
        # check cache first
        cached = cache.get_cached(question)
        if cached:
            logger.info("Serving from cache")
            result = cached
            sql = "(cached query)"
        else:
            agent_result = run_agent(question)
            if agent_result["error"]:
                post_message(
                    channel,
                    format_error_for_slack(question, agent_result["error"])
                )
                return
            result = agent_result["result"]
            sql = agent_result["sql"]
            cache.set_cached(question, result)

        blocks = format_results_for_slack(question, sql, result)
        post_message(channel, blocks)

    except Exception as e:
        logger.error(f"Unexpected error processing query: {e}")
        post_message(
            channel,
            format_error_for_slack(question, str(e))
        )


# --- Slash command endpoint ---
@router.post("/slack/command")
async def slash_command(
    request: Request,
    background_tasks: BackgroundTasks,
    body: bytes = Depends(slack_auth)
):
    # Slack sends form-encoded body
    from urllib.parse import parse_qs
    params = parse_qs(body.decode("utf-8"))
    question = params.get("text", [""])[0].strip()
    channel_id = params.get("channel_id", [""])[0]
    response_url = params.get("response_url", [""])[0]

    if not question:
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": "Please provide a question. Usage: `/ask-data show revenue by region`"
        })

    # immediate ack to Slack (must respond within 3 seconds)
    background_tasks.add_task(process_query, question, channel_id, response_url)

    return JSONResponse(content={
        "response_type": "ephemeral",
        "text": f":hourglass: Got it! Running: _{question}_"
    })


# --- Interactivity endpoint (CSV button) ---
@router.post("/slack/interactivity")
async def interactivity(
    request: Request,
    background_tasks: BackgroundTasks,
    body: bytes = Depends(slack_auth)
):
    from urllib.parse import parse_qs
    params = parse_qs(body.decode("utf-8"))
    payload = json.loads(params.get("payload", ["{}"])[0])

    actions = payload.get("actions", [])
    if not actions:
        return JSONResponse(content={"ok": True})

    action = actions[0]
    if action.get("action_id") != "export_csv":
        return JSONResponse(content={"ok": True})

    question = action.get("value", "")
    channel_id = payload.get("channel", {}).get("id", "")

    background_tasks.add_task(handle_csv_export, question, channel_id)

    # immediate ack
    return JSONResponse(content={"ok": True})


def handle_csv_export(question: str, channel: str):
    logger.info(f"CSV export requested for: '{question}'")
    cached = cache.get_cached(question)
    if not cached:
        post_message(channel, format_error_for_slack(
            question,
            "Result expired from cache. Please run the query again."
        ))
        return

    csv_file = generate_csv(cached)
    filename = question[:40].replace(" ", "_") + ".csv"
    upload_csv(
        channel=channel,
        file=csv_file,
        filename=filename,
        title=f"Export: {question[:60]}"
    )