import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from image_generator import ImageGenerator
from prompt_builder import build_prompt
from word_manager import WordManager

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

word_manager = WordManager()
image_generator = ImageGenerator()
connected_presenters: list[WebSocket] = []

STATIC_DIR = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Background image-generation loop
# ---------------------------------------------------------------------------

_last_image_b64: str = ""  # cache so new WS connections get something immediately


async def _broadcast(payload: dict):
    data = json.dumps(payload)
    dead = []
    for ws in connected_presenters:
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_presenters.remove(ws)


async def image_generation_loop():
    global _last_image_b64
    while True:
        await asyncio.sleep(5)
        top_words = word_manager.get_top_words(20)
        word_texts = [w["text"] for w in top_words[:8]]
        positive, negative = build_prompt(word_texts)

        # Run blocking generation in thread pool so we don't block the event loop
        loop = asyncio.get_event_loop()
        b64 = await loop.run_in_executor(
            None, image_generator.generate, positive, negative
        )
        _last_image_b64 = b64

        await _broadcast(
            {
                "type": "update",
                "words": top_words,
                "image": b64,
                "total_submissions": word_manager.total_submissions(),
            }
        )


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(image_generation_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

# Serve static files (CSS, etc.)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return RedirectResponse(url="/presenter")


@app.get("/presenter")
async def presenter():
    return FileResponse(STATIC_DIR / "presenter.html")


@app.get("/input")
async def input_page():
    return FileResponse(STATIC_DIR / "input.html")


class WordSubmission(BaseModel):
    word: str


@app.post("/submit")
async def submit_word(submission: WordSubmission):
    word = submission.word.strip()
    if not word or len(word) > 60:
        return {"success": False, "error": "Invalid word"}

    count = word_manager.add_word(word)
    total = word_manager.total_submissions()
    top_words = word_manager.get_top_words(20)

    # Immediately broadcast updated word cloud (no new image yet)
    await _broadcast(
        {
            "type": "words_update",
            "words": top_words,
            "image": _last_image_b64,
            "total_submissions": total,
        }
    )

    return {"success": True, "count": count, "total": total}


@app.get("/words")
async def get_words():
    return {
        "words": word_manager.get_top_words(20),
        "total": word_manager.total_submissions(),
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_presenters.append(websocket)

    # Send current state immediately on connect
    try:
        top_words = word_manager.get_top_words(20)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "update",
                    "words": top_words,
                    "image": _last_image_b64,
                    "total_submissions": word_manager.total_submissions(),
                }
            )
        )
        while True:
            # Keep connection alive; client doesn't send data
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in connected_presenters:
            connected_presenters.remove(websocket)
