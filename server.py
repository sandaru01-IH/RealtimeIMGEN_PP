import asyncio
import base64
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from beauty_scorer import BeautyScorer
from image_generator import ImageGenerator
from prompt_builder import build_prompt
from word_manager import WordManager

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

word_manager    = WordManager()
image_generator = ImageGenerator()
beauty_scorer   = BeautyScorer()
connected_presenters: list[WebSocket] = []

STATIC_DIR = Path(__file__).parent / "static"

# ---------------------------------------------------------------------------
# Background loops
# ---------------------------------------------------------------------------

_last_image_b64: str  = ""
_last_score:     dict = {}   # cached so new WS connections get latest score


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
    global _last_image_b64, _last_score
    while True:
        await asyncio.sleep(5)

        # Hold original photo until first word is submitted
        if image_generator.has_base_image() and word_manager.total_submissions() == 0:
            continue

        top_words  = word_manager.get_top_words(20)
        word_texts = [w["text"] for w in top_words[:8]]
        is_img2img = image_generator.has_base_image()
        positive, negative = build_prompt(word_texts, img2img=is_img2img)

        loop = asyncio.get_event_loop()

        # 1 — Generate image (blocking, run in thread pool)
        b64 = await loop.run_in_executor(
            None, image_generator.generate, positive, negative
        )
        _last_image_b64 = b64

        # Broadcast image immediately so presenter updates without waiting for scoring
        await _broadcast({
            "type":              "update",
            "words":             top_words,
            "image":             b64,
            "total_submissions": word_manager.total_submissions(),
            "has_base_image":    image_generator.has_base_image(),
            "score":             _last_score,   # send previous score while new one computes
        })

        # 2 — Score in background (non-blocking — presenter already has new image)
        score = await loop.run_in_executor(None, beauty_scorer.score, b64)
        if score:
            _last_score = score
            # Push score update separately so it arrives as soon as it's ready
            await _broadcast({
                "type":  "score_update",
                "score": score,
            })


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

    count    = word_manager.add_word(word)
    total    = word_manager.total_submissions()
    top_words = word_manager.get_top_words(20)

    await _broadcast({
        "type":              "words_update",
        "words":             top_words,
        "image":             _last_image_b64,
        "total_submissions": total,
        "has_base_image":    image_generator.has_base_image(),
        "score":             _last_score,
    })

    return {"success": True, "count": count, "total": total}


@app.get("/words")
async def get_words():
    return {
        "words": word_manager.get_top_words(20),
        "total": word_manager.total_submissions(),
    }


@app.post("/upload-base-image")
async def upload_base_image(file: UploadFile = File(...)):
    try:
        raw_name = file.filename or "upload.jpg"
        ext = Path(raw_name).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"

        contents = await file.read()
        if len(contents) == 0:
            return {"success": False, "error": "Uploaded file is empty"}
        if len(contents) > 20 * 1024 * 1024:
            return {"success": False, "error": "Image too large (max 20 MB)"}

        dest = STATIC_DIR / f"base_image{ext}"
        dest.write_bytes(contents)

        ok = image_generator.set_base_image(contents, f"street_base{ext}")

        global _last_image_b64
        _last_image_b64 = base64.b64encode(contents).decode()
        await _broadcast({
            "type":              "base_image_set",
            "image":             _last_image_b64,
            "has_base_image":    True,
            "words":             word_manager.get_top_words(20),
            "total_submissions": word_manager.total_submissions(),
            "score":             _last_score,
        })

        return {
            "success":          True,
            "comfyui_uploaded": ok,
            "filename":         f"base_image{ext}",
            "message":          "Base image set — img2img mode active." if ok else
                                "Image saved. ComfyUI upload failed — will retry on next generation.",
        }

    except Exception as e:
        print(f"[upload-base-image] Error: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/upload-base-image")
async def clear_base_image():
    image_generator.clear_base_image()
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = STATIC_DIR / f"base_image{ext}"
        if p.exists():
            p.unlink()
    return {"success": True, "message": "Base image cleared. Back to txt2img mode."}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_presenters.append(websocket)

    try:
        await websocket.send_text(json.dumps({
            "type":              "update",
            "words":             word_manager.get_top_words(20),
            "image":             _last_image_b64,
            "total_submissions": word_manager.total_submissions(),
            "has_base_image":    image_generator.has_base_image(),
            "score":             _last_score,
        }))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in connected_presenters:
            connected_presenters.remove(websocket)
