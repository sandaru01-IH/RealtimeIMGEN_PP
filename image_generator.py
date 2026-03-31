import base64
import io
import json
import time
import uuid
import requests


COMFYUI_BASE = "http://127.0.0.1:8188"
WORKFLOW_PATH = "comfyui_workflow.json"
WORKFLOW_IMG2IMG_PATH = "comfyui_workflow_img2img.json"


def _grey_placeholder() -> str:
    """Return a base64-encoded grey PNG with 'ComfyUI not connected' text."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (832, 512), color=(40, 40, 40))
        draw = ImageDraw.Draw(img)
        draw.text((832 // 2, 512 // 2), "ComfyUI not connected", fill=(120, 120, 120), anchor="mm")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        GREY_PNG_B64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
            "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        return GREY_PNG_B64


class ImageGenerator:
    def __init__(self):
        self._workflow: dict | None = None
        self._workflow_img2img: dict | None = None
        self._base_image_filename: str | None = None  # filename in ComfyUI input/
        self._base_image_b64: str | None = None       # to use as fallback placeholder
        self._load_workflows()

    def _load_workflows(self):
        try:
            with open(WORKFLOW_PATH, "r") as f:
                self._workflow = json.load(f)
        except Exception as e:
            print(f"[ImageGenerator] Could not load txt2img workflow: {e}")

        try:
            with open(WORKFLOW_IMG2IMG_PATH, "r") as f:
                self._workflow_img2img = json.load(f)
        except Exception as e:
            print(f"[ImageGenerator] Could not load img2img workflow: {e}")

    def set_base_image(self, image_bytes: bytes, original_filename: str = "street_base.png") -> bool:
        """
        Upload a base image to ComfyUI input folder.
        Returns True on success, False if ComfyUI is unreachable.
        Also caches a base64 copy as a fallback placeholder.
        """
        # Cache base64 regardless of ComfyUI state
        self._base_image_b64 = base64.b64encode(image_bytes).decode()

        try:
            resp = requests.post(
                f"{COMFYUI_BASE}/upload/image",
                files={"image": (original_filename, image_bytes, "image/png")},
                data={"overwrite": "true", "type": "input"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._base_image_filename = data.get("name", original_filename)
            print(f"[ImageGenerator] Base image uploaded: {self._base_image_filename}")
            return True
        except Exception as e:
            print(f"[ImageGenerator] Base image upload failed: {e}")
            # Store the name anyway so we can retry on next generation
            self._base_image_filename = original_filename
            return False

    def has_base_image(self) -> bool:
        return self._base_image_filename is not None

    def clear_base_image(self):
        self._base_image_filename = None
        self._base_image_b64 = None

    def _active_workflow(self) -> dict | None:
        if self._base_image_filename and self._workflow_img2img:
            return self._workflow_img2img
        return self._workflow

    def _inject_prompts(self, workflow: dict, positive: str, negative: str) -> dict:
        wf = json.loads(json.dumps(workflow))  # deep copy
        for node in wf.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs", {})
            if inputs.get("text") == "POSITIVE_PROMPT_HERE":
                inputs["text"] = positive
            elif inputs.get("text") == "NEGATIVE_PROMPT_HERE":
                inputs["text"] = negative
            elif inputs.get("image") == "BASE_IMAGE_FILENAME":
                inputs["image"] = self._base_image_filename
        return wf

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
            return resp.json().get("prompt_id")
        except Exception as e:
            print(f"[ImageGenerator] Queue failed: {e}")
            return None

    def _poll_history(self, prompt_id: str, timeout: int = 90) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(f"{COMFYUI_BASE}/history/{prompt_id}", timeout=10)
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
            self._load_workflows()

        # Check ComfyUI is reachable
        try:
            requests.get(f"{COMFYUI_BASE}/system_stats", timeout=3)
        except Exception:
            print("[ImageGenerator] ComfyUI not reachable, returning placeholder.")
            # If we have a base image cached, return it as fallback
            return self._base_image_b64 if self._base_image_b64 else _grey_placeholder()

        workflow = self._active_workflow()
        if workflow is None:
            return self._base_image_b64 if self._base_image_b64 else _grey_placeholder()

        mode = "img2img" if self._base_image_filename else "txt2img"
        print(f"[ImageGenerator] Generating ({mode})...")

        wf = self._inject_prompts(workflow, prompt, negative_prompt)
        prompt_id = self._queue_prompt(wf)
        if not prompt_id:
            return self._base_image_b64 if self._base_image_b64 else _grey_placeholder()

        result = self._poll_history(prompt_id)
        if not result:
            print("[ImageGenerator] Timed out waiting for image.")
            return self._base_image_b64 if self._base_image_b64 else _grey_placeholder()

        try:
            for node_output in result.get("outputs", {}).values():
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

        return self._base_image_b64 if self._base_image_b64 else _grey_placeholder()
