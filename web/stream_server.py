import math
from ast import literal_eval
from contextlib import asynccontextmanager
from logging import getLogger
from mimetypes import guess_type
from os import getenv

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pyrogram import Client

from bot.core.config_manager import Config
from web.stream_utils import (
    build_content_disposition,
    get_file_name,
    get_media_from_message,
    verify_stream_hash,
)


LOGGER = getLogger(__name__)

Config.load()

STREAM_CLIENTS = []


def _is_meaningful_stream_value(key, value):
    if value is None:
        return False

    if key == "STREAM_BASE_URL":
        return bool(str(value).strip())

    if key in {"STREAM_PORT", "STREAM_CHANNEL"}:
        try:
            return int(value) != 0
        except Exception:
            return False

    if key == "STREAM_BOT_TOKENS":
        return isinstance(value, list) or bool(str(value).strip())

    return True


def _apply_stream_config(data, source):
    if not data:
        return

    for key in (
        "STREAM_BASE_URL",
        "STREAM_PORT",
        "STREAM_CHANNEL",
        "STREAM_BOT_TOKENS",
    ):
        if key not in data:
            continue

        value = data[key]

        if not _is_meaningful_stream_value(key, value):
            continue

        try:
            Config.set(key, value)
        except Exception:
            if key == "STREAM_BOT_TOKENS" and isinstance(value, list):
                Config.STREAM_BOT_TOKENS = value
            else:
                LOGGER.error(f"Invalid {key} from {source}: {value}")


def _load_stream_config_from_env():
    env_data = {}

    if getenv("STREAM_BASE_URL") is not None:
        env_data["STREAM_BASE_URL"] = getenv("STREAM_BASE_URL")

    if getenv("STREAM_PORT") is not None:
        env_data["STREAM_PORT"] = getenv("STREAM_PORT")

    if getenv("STREAM_CHANNEL") is not None:
        env_data["STREAM_CHANNEL"] = getenv("STREAM_CHANNEL")

    if getenv("STREAM_BOT_TOKENS") is not None:
        try:
            env_data["STREAM_BOT_TOKENS"] = literal_eval(
                getenv("STREAM_BOT_TOKENS") or "[]"
            )
        except Exception:
            env_data["STREAM_BOT_TOKENS"] = []

    _apply_stream_config(env_data, "env")


async def _load_stream_config_from_mongo():
    if not Config.DATABASE_URL:
        return

    try:
        from pymongo import AsyncMongoClient
        from pymongo.server_api import ServerApi
    except Exception as error:
        LOGGER.error(f"Mongo import failed for stream server: {error}")
        return

    client = None

    try:
        bot_id = Config.BOT_TOKEN.split(":", 1)[0]

        client = AsyncMongoClient(
            Config.DATABASE_URL,
            server_api=ServerApi("1"),
            connectTimeoutMS=60000,
            serverSelectionTimeoutMS=60000,
        )

        db = client[Config.DATABASE_NAME]

        deploy_doc = await db.settings.deployConfig.find_one(
            {"_id": bot_id},
            {"_id": 0},
        )

        config_doc = await db.settings.config.find_one(
            {"_id": bot_id},
            {"_id": 0},
        )

        _apply_stream_config(deploy_doc, "mongo deployConfig")
        _apply_stream_config(config_doc, "mongo settings.config")

    except Exception as error:
        LOGGER.error(f"Unable to load stream config from Mongo: {error}")

    finally:
        if client is not None:
            await client.close()


async def load_stream_runtime_config():
    # Env is a fallback passed by the main bot process.
    # Mongo runtime config is applied after it, so it has priority.
    _load_stream_config_from_env()
    await _load_stream_config_from_mongo()

    Config.STREAM_BASE_URL = str(Config.STREAM_BASE_URL or "").rstrip("/")

    LOGGER.info(
        f"Stream config: base={Config.STREAM_BASE_URL}, "
        f"port={Config.STREAM_PORT}, "
        f"channel={Config.STREAM_CHANNEL}, "
        f"extra_clients={len(Config.STREAM_BOT_TOKENS)}"
    )


class StreamClient:
    def __init__(self, client):
        self.client = client
        self.load = 0


def select_client():
    if not STREAM_CLIENTS:
        raise HTTPException(status_code=503, detail="No stream client is running")

    return min(STREAM_CLIENTS, key=lambda item: item.load)


async def start_clients():
    tokens = []

    # If STREAM_BOT_TOKENS is configured, main BOT_TOKEN is not used for streaming.
    # If empty, main BOT_TOKEN is used as a fallback.
    stream_tokens = Config.STREAM_BOT_TOKENS or [Config.BOT_TOKEN]

    for token in stream_tokens:
        if token and token not in tokens:
            tokens.append(token)

    if Config.STREAM_BOT_TOKENS:
        LOGGER.info("Stream client mode: STREAM_BOT_TOKENS only, main BOT_TOKEN excluded")
    else:
        LOGGER.info("Stream client mode: main BOT_TOKEN fallback")

    for index, token in enumerate(tokens):
        name = f"stream_{index}_{token.split(':', 1)[0]}"

        client = Client(
            name,
            api_id=Config.TELEGRAM_API,
            api_hash=Config.TELEGRAM_HASH,
            bot_token=token,
            proxy=Config.TG_PROXY or None,
            in_memory=True,
            no_updates=True,
            sleep_threshold=60,
        )

        await client.start()
        STREAM_CLIENTS.append(StreamClient(client))

    LOGGER.info(f"Started {len(STREAM_CLIENTS)} stream client(s)")


async def stop_clients():
    for item in STREAM_CLIENTS:
        try:
            await item.client.stop()
        except Exception as error:
            LOGGER.error(f"Unable to stop stream client: {error}")

    STREAM_CLIENTS.clear()


@asynccontextmanager
async def lifespan(app):
    await load_stream_runtime_config()
    await start_clients()
    yield
    await stop_clients()


app = FastAPI(lifespan=lifespan)


def parse_byte_range(range_header, file_size):
    if not range_header:
        return 0, file_size - 1, False

    range_value = range_header.strip()

    if not range_value.lower().startswith("bytes=") or "," in range_value:
        raise ValueError("Invalid Range header")

    start_text, end_text = range_value[6:].split("-", 1)

    if not start_text:
        length = int(end_text)

        if length <= 0:
            raise ValueError("Invalid suffix range")

        start = max(file_size - length, 0)
        end = file_size - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1

    if start < 0 or start >= file_size or end < start:
        raise ValueError("Unsatisfiable range")

    return start, min(end, file_size - 1), True


async def get_file_properties(client, chat_id, message_id):
    message = await client.get_messages(chat_id, message_id)

    if not message or getattr(message, "empty", False):
        raise FileNotFoundError("Telegram message was not found")

    _, media = get_media_from_message(message)

    if media is None:
        raise FileNotFoundError("Telegram message has no supported media")

    return message, media


async def iter_file(client, message, start, end, chunk_size=1024 * 1024):
    chunk_offset = start // chunk_size
    aligned_start = chunk_offset * chunk_size
    first_cut = start - aligned_start

    part_count = math.ceil((end + 1 - aligned_start) / chunk_size)
    last_cut = end + 1 - aligned_start - ((part_count - 1) * chunk_size)

    part = 0

    async for chunk in client.stream_media(
        message,
        offset=chunk_offset,
        limit=part_count,
    ):
        if part_count == 1:
            yield chunk[first_cut:last_cut]
        elif part == 0:
            yield chunk[first_cut:]
        elif part == part_count - 1:
            yield chunk[:last_cut]
        else:
            yield chunk

        part += 1


@app.get("/")
async def root():
    return JSONResponse(
        {
            "status": "running",
            "base": Config.STREAM_BASE_URL,
            "channel": Config.STREAM_CHANNEL,
            "clients": len(STREAM_CLIENTS),
            "loads": [item.load for item in STREAM_CLIENTS],
        }
    )


async def serve_telegram_file(
    request,
    chat_id,
    message_id,
    file_hash,
    disposition,
):
    if not Config.STREAM_CHANNEL:
        raise HTTPException(status_code=503, detail="Streaming is disabled")

    worker = select_client()

    try:
        message, media = await get_file_properties(
            worker.client,
            chat_id,
            message_id,
        )
    except Exception as error:
        LOGGER.error(f"Unable to get Telegram file: {error}")
        raise HTTPException(status_code=404, detail="Telegram file not found") from error

    if not verify_stream_hash(file_hash, chat_id, message_id, media):
        raise HTTPException(status_code=403, detail="Invalid stream link")

    file_size = getattr(media, "file_size", 0)

    if not file_size:
        raise HTTPException(status_code=404, detail="Telegram file size is missing")

    try:
        start, end, partial = parse_byte_range(
            request.headers.get("range"),
            file_size,
        )
    except Exception:
        raise HTTPException(
            status_code=416,
            detail="Requested range is not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        ) from None

    file_name = get_file_name(message)
    mime_type = (
        getattr(media, "mime_type", "")
        or guess_type(file_name)[0]
        or "application/octet-stream"
    )

    content_length = end - start + 1

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Disposition": build_content_disposition(disposition, file_name),
    }

    if partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    status_code = 206 if partial else 200

    if request.method == "HEAD":
        return Response(
            status_code=status_code,
            media_type=mime_type,
            headers=headers,
        )

    worker.load += 1

    async def body():
        try:
            async for part in iter_file(worker.client, message, start, end):
                yield part
        finally:
            worker.load -= 1

    return StreamingResponse(
        body(),
        status_code=status_code,
        media_type=mime_type,
        headers=headers,
    )


@app.api_route(
    "/stream/{chat_id}/{message_id}/{token}/{requested_name:path}",
    methods=["GET", "HEAD"],
)
async def legacy_stream(
    request: Request,
    chat_id: int,
    message_id: int,
    token: str,
    requested_name: str,
):
    return await serve_telegram_file(
        request,
        chat_id,
        message_id,
        token,
        "inline",
    )


@app.api_route(
    "/download/{chat_id}/{message_id}/{token}/{requested_name:path}",
    methods=["GET", "HEAD"],
)
async def legacy_download(
    request: Request,
    chat_id: int,
    message_id: int,
    token: str,
    requested_name: str,
):
    return await serve_telegram_file(
        request,
        chat_id,
        message_id,
        token,
        "attachment",
    )


@app.api_route(
    "/download/{message_id:int}/{requested_name:path}",
    methods=["GET", "HEAD"],
)
async def public_download(
    request: Request,
    message_id: int,
    requested_name: str,
    file_hash: str = Query("", alias="hash"),
):
    return await serve_telegram_file(
        request,
        Config.STREAM_CHANNEL,
        message_id,
        file_hash,
        "attachment",
    )


@app.api_route(
    "/{message_id:int}/{requested_name:path}",
    methods=["GET", "HEAD"],
)
async def public_stream(
    request: Request,
    message_id: int,
    requested_name: str,
    file_hash: str = Query("", alias="hash"),
):
    return await serve_telegram_file(
        request,
        Config.STREAM_CHANNEL,
        message_id,
        file_hash,
        "inline",
    )


@app.api_route(
    "/{short_code}",
    methods=["GET", "HEAD"],
)
async def public_short(
    request: Request,
    short_code: str,
):
    if len(short_code) <= 6:
        raise HTTPException(status_code=404, detail="Not Found")

    file_hash = short_code[:6]
    message_id_text = short_code[6:]

    if not message_id_text.isdigit():
        raise HTTPException(status_code=404, detail="Not Found")

    return await serve_telegram_file(
        request,
        Config.STREAM_CHANNEL,
        int(message_id_text),
        file_hash,
        "inline",
    )
