# Street Cloud

A real-time participatory urban design tool for workshops. Audience members
submit words describing their ideal street; the app shows a live animated word
cloud and regenerates a street image every 5 seconds using local Stable
Diffusion (ComfyUI + SDXL Turbo).

## Affiliation

**SmartMind UI & AI Group**  
**Urban Simulation Lab**  
Department of Town & Country Planning  
University of Moratuwa, Sri Lanka
---

## Architecture

```
Audience phones  ──POST /submit──►  FastAPI (port 8000)
                                       │
Presenter screen ──WS /ws──────────►  │  ◄── background loop (every 5 s)
                                       │         │
                                   WordManager   ImageGenerator
                                                      │
                                               ComfyUI (port 8188)
                                               SDXL Turbo model
```

---

## Setup

### 1 — Install ComfyUI

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt
```

### 2 — Download SDXL Turbo model

Download from HuggingFace and place in `ComfyUI/models/checkpoints/`:

```
https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors
```

Direct wget:
```bash
wget -P ComfyUI/models/checkpoints/ \
  "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors"
```

### 3 — Run ComfyUI

```bash
cd ComfyUI
python main.py --listen
```

ComfyUI will be available at `http://127.0.0.1:8188`.
If it is not running, Street Cloud falls back to word-cloud-only mode
(a grey placeholder is shown instead of generated images).

### 4 — Install Python dependencies

```bash
cd /path/to/street-cloud
pip install -r requirements.txt
```

### 5 — Run Street Cloud

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## Usage

| URL | Who uses it |
|-----|-------------|
| `http://localhost:8000/presenter` | Presenter screen / projector |
| `http://<YOUR_LOCAL_IP>:8000/input` | Audience phones |

### Finding your local IP

**Windows:**
```
ipconfig
```
Look for `IPv4 Address` under your Wi-Fi adapter (e.g., `192.168.1.42`).

**macOS / Linux:**
```bash
ip route get 1 | awk '{print $7}'
# or
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Share `http://192.168.1.42:8000/input` via QR code or written on a board.

---

## File structure

```
street-cloud/
├── server.py               # FastAPI app + WebSocket + background loop
├── word_manager.py         # Thread-safe word counter
├── prompt_builder.py       # Builds SD prompts from top words
├── image_generator.py      # ComfyUI API client
├── comfyui_workflow.json   # SDXL Turbo ComfyUI workflow
├── requirements.txt
└── static/
    ├── presenter.html      # Full-screen presenter view
    ├── input.html          # Audience submission page
    └── style.css           # Shared dark theme styles
```

---

## Configuration

| Setting | Location | Default |
|---------|----------|---------|
| Image generation interval | `server.py` → `image_generation_loop` | 5 s |
| ComfyUI URL | `image_generator.py` → `COMFYUI_BASE` | `http://127.0.0.1:8188` |
| Model filename | `comfyui_workflow.json` node `"1"` | `sd_xl_turbo_1.0_fp16.safetensors` |
| Image size | `comfyui_workflow.json` node `"5"` | 832 × 512 |
| Top words for prompt | `server.py` → `word_texts` slice | 8 |
| Words shown in cloud | `server.py` → `get_top_words` | 20 |

---

## Troubleshooting

**Grey placeholder shown instead of images**
- Confirm ComfyUI is running: open `http://127.0.0.1:8188` in your browser.
- Check the console where `uvicorn` is running for `[ImageGenerator]` errors.

**Audience can't reach the input page**
- Make sure both devices are on the same Wi-Fi network.
- Check your firewall allows inbound connections on port 8000.
- Use `ipconfig` (Windows) or `ifconfig` (macOS/Linux) to confirm your IP.

**Word cloud not rendering**
- The presenter page loads D3 and d3-cloud from CDN — internet access is
  required the first time. After that you can cache the scripts locally if
  needed.
