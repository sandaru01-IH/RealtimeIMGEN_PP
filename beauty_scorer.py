"""
beauty_scorer.py
────────────────
Scores a street image against Christopher Alexander's 15 properties of
living structure using Qwen2.5VL running locally via Ollama.

Returns a structured dict with per-property scores (0–1), a total (0–15),
and a one-sentence summary.

Fallback: if Ollama is not running or the model is not available, returns
None so the caller can skip the display gracefully.
"""

import base64
import json
import re
import time

try:
    import ollama as _ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# ── Configuration ────────────────────────────────────────────────────────────

MODEL = "qwen2.5vl:3b"

# The 15 properties in display order, with short labels for the UI
PROPERTIES = [
    ("levels_of_scale",        "Levels of Scale"),
    ("strong_centers",         "Strong Centers"),
    ("boundaries",             "Boundaries"),
    ("alternating_repetition", "Alternating Repetition"),
    ("positive_space",         "Positive Space"),
    ("good_shape",             "Good Shape"),
    ("local_symmetries",       "Local Symmetries"),
    ("deep_interlock",         "Deep Interlock"),
    ("contrast",               "Contrast"),
    ("gradients",              "Gradients"),
    ("roughness",              "Roughness"),
    ("echoes",                 "Echoes"),
    ("the_void",               "The Void"),
    ("simplicity",             "Simplicity"),
    ("not_separateness",       "Not-Separateness"),
]

PROPERTY_KEYS = [p[0] for p in PROPERTIES]

# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert urban design quality assessor applying Christopher Alexander's theory of living structure to street-level imagery.

Score the image against each of the 15 fundamental properties of living structure.
Give each property a score from 0.0 to 1.0:
  0.0 = completely absent
  0.5 = moderately present
  1.0 = strongly present

Properties:
1. levels_of_scale       — hierarchy of sizes from very small to very large elements
2. strong_centers        — focal points, nodes, or anchors that draw attention
3. boundaries            — clear edges that define and separate spaces
4. alternating_repetition — rhythmic patterns with variation between elements
5. positive_space        — well-shaped, purposeful spaces between solid elements
6. good_shape            — each element has a satisfying, coherent form
7. local_symmetries      — small-scale balance and symmetry in parts of the scene
8. deep_interlock        — elements interpenetrate; figure and ground are ambiguous
9. contrast              — clear differentiation between light/dark, hard/soft, old/new
10. gradients            — gradual transitions from one condition to another
11. roughness            — natural irregularity, handmade quality, imperfection
12. echoes               — similar angles, shapes, or patterns that repeat across scales
13. the_void             — calm, uncluttered areas of visual rest
14. simplicity           — inner calm and order beneath surface complexity
15. not_separateness     — the scene feels connected to its wider surroundings

Respond ONLY with valid JSON. No explanation, no markdown, just the JSON object:
{
  "scores": {
    "levels_of_scale": <float>,
    "strong_centers": <float>,
    "boundaries": <float>,
    "alternating_repetition": <float>,
    "positive_space": <float>,
    "good_shape": <float>,
    "local_symmetries": <float>,
    "deep_interlock": <float>,
    "contrast": <float>,
    "gradients": <float>,
    "roughness": <float>,
    "echoes": <float>,
    "the_void": <float>,
    "simplicity": <float>,
    "not_separateness": <float>
  },
  "total": <sum of all 15 scores, float>,
  "summary": "<one sentence urban design assessment>"
}"""

USER_PROMPT = "Score this street scene using the 15 properties of living structure."

# ── Scorer class ─────────────────────────────────────────────────────────────

RETRY_INTERVAL = 30  # seconds between availability rechecks when unavailable


class BeautyScorer:
    def __init__(self):
        self._available: bool = False
        self._last_check: float = 0.0   # epoch seconds of last check

    def _check_available(self) -> bool:
        if not OLLAMA_AVAILABLE:
            print("[BeautyScorer] ollama Python package not installed.")
            return False
        try:
            models = _ollama.list()
            # models.models is a list of Model objects; .model is the name string
            names = [m.model for m in models.models]
            print(f"[BeautyScorer] Ollama models found: {names}")
            # Accept any name that starts with or contains the base model name
            base = MODEL.split(":")[0]   # e.g. "qwen2.5vl"
            match = any(base in n for n in names)
            if match:
                print(f"[BeautyScorer] Model '{MODEL}' confirmed available.")
            else:
                print(f"[BeautyScorer] Model '{MODEL}' not found in Ollama list.")
            return match
        except Exception as e:
            print(f"[BeautyScorer] Ollama not reachable: {e}")
            return False

    def is_available(self) -> bool:
        # Always recheck if not available (with cooldown to avoid hammering)
        if not self._available:
            now = time.time()
            if now - self._last_check >= RETRY_INTERVAL:
                self._last_check = now
                self._available = self._check_available()
        return self._available

    def score(self, image_b64: str) -> dict | None:
        """
        Score a base64-encoded image.
        Returns a dict with keys: scores (dict), total (float), summary (str),
        properties (list of {key, label, value} for UI rendering).
        Returns None if Ollama/model is unavailable.
        """
        if not self.is_available():
            print("[BeautyScorer] Ollama or model not available — skipping.")
            return None

        try:
            t0 = time.time()
            response = _ollama.chat(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": USER_PROMPT,
                        "images": [image_b64],
                    },
                ],
                options={"temperature": 0.1},
            )
            elapsed = round(time.time() - t0, 1)
            raw = response["message"]["content"].strip()

            result = _parse_response(raw)
            if result:
                print(f"[BeautyScorer] Score: {result['total']:.1f}/15 ({elapsed}s)")
            return result

        except Exception as e:
            print(f"[BeautyScorer] Error: {e}")
            self._available = False  # force recheck on next cycle
            self._last_check = 0.0
            return None


def _parse_response(raw: str) -> dict | None:
    """Extract and validate JSON from the model response."""
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    # Find the first { ... } block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        print(f"[BeautyScorer] No JSON found in response: {raw[:200]}")
        return None

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        print(f"[BeautyScorer] JSON parse error: {e}")
        return None

    scores = data.get("scores", {})
    if not scores:
        return None

    # Clamp all scores to [0, 1]
    clean = {}
    for key in PROPERTY_KEYS:
        val = scores.get(key, 0.0)
        try:
            clean[key] = max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            clean[key] = 0.0

    total = round(sum(clean.values()), 2)

    # Build UI-friendly list: [{key, label, value, pct}]
    props_ui = [
        {
            "key":   key,
            "label": label,
            "value": round(clean[key], 2),
            "pct":   int(clean[key] * 100),
        }
        for key, label in PROPERTIES
    ]

    # Sort so weakest properties appear at bottom
    props_ui_sorted = sorted(props_ui, key=lambda x: x["value"], reverse=True)

    return {
        "scores":     clean,
        "total":      total,
        "summary":    data.get("summary", ""),
        "properties": props_ui_sorted,
    }
