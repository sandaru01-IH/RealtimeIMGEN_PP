import base64
import io
import json
import time
import uuid
import requests


COMFYUI_BASE = "http://127.0.0.1:8188"
WORKFLOW_PATH = "comfyui_workflow.json"


def _grey_placeholder() -> str:
    """Return a base64-encoded grey PNG with 'ComfyUI not connected' text."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (832, 512), color=(40, 40, 40))
        draw = ImageDraw.Draw(img)
        msg = "ComfyUI not connected"
        draw.text((832 // 2, 512 // 2), msg, fill=(120, 120, 120), anchor="mm")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        # Minimal 1x1 grey PNG fallback (no Pillow required)
        GREY_PNG_B64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        return GREY_PNG_B64


class ImageGenerator:
    def __init__(self):
        self._workflow: dict | None = None
        self._load_workflow()

    def _load_workflow(self):
        try:
            with open(WORKFLOW_PATH, "r") as f:
                self._workflow = json.load(f)
        except Exception as e:
            print(f"[ImageGenerator] Could not load workflow: {e}")
            self._workflow = None

    def _inject_prompts(self, positive: str, negative: str) -> dict:
        workflow = json.loads(json.dumps(self._workflow))  # deep copy
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs", {})
            if inputs.get("text") == "POSITIVE_PROMPT_HERE":
                inputs["text"] = positive
            elif inputs.get("text") == "NEGATIVE_PROMPT_HERE":
                inputs["text"] = negative
        return workflow

    def _queue_prompt(self, workflow: dict) -> str | None:
        client_id = str(uuid.uuid4())
        payload = {"prompt": workflow, "client_id": client_id}
        try:
            resp = requests.post(
                f"{COMFYUI_BASE}/prompt",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("prompt_id")
        except Exception as e:
            print(f"[ImageGenerator] Queue failed: {e}")
            return None

    def _poll_history(self, prompt_id: str, timeout: int = 60) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(
                    f"{COMFYUI_BASE}/history/{prompt_id}", timeout=10
                )
                resp.raise_for_status()
                history = resp.json()
                if prompt_id in history:
                    return history[prompt_id]
            except Exception as e:
                print(f"[ImageGenerator] Poll error: {e}")
            time.sleep(1)
        return None

    def _fetch_image(self, filename: str, subfolder: str, folder_type: str) -> str | None:
        try:
            resp = requests.get(
                f"{COMFYUI_BASE}/view",
                params={"filename": filename, "subfolder": subfolder, "type": folder_type},
                timeout=15,
            )
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode()
        except Exception as e:
            print(f"[ImageGenerator] Fetch image error: {e}")
            return None

    def generate(self, prompt: str, negative_prompt: str) -> str:
        if self._workflow is None:
            self._load_workflow()

        if self._workflow is None:
            print("[ImageGenerator] No workflow available, returning placeholder.")
            return _grey_placeholder()

        # Check ComfyUI is reachable
        try:
            requests.get(f"{COMFYUI_BASE}/system_stats", timeout=3)
        except Exception:
            print("[ImageGenerator] ComfyUI not reachable, returning placeholder.")
            return _grey_placeholder()

        workflow = self._inject_prompts(prompt, negative_prompt)
        prompt_id = self._queue_prompt(workflow)
        if not prompt_id:
            return _grey_placeholder()

        result = self._poll_history(prompt_id)
        if not result:
            print("[ImageGenerator] Timed out waiting for image.")
            return _grey_placeholder()

        # Extract image from outputs
        try:
            outputs = result.get("outputs", {})
            for node_output in outputs.values():
                images = node_output.get("images", [])
                if images:
                    img_info = images[0]
                    b64 = self._fetch_image(
                        img_info["filename"],
                        img_info.get("subfolder", ""),
                        img_info.get("type", "output"),
                    )
                    if b64:
                        return b64
        except Exception as e:
            print(f"[ImageGenerator] Output parse error: {e}")

        return _grey_placeholder()
