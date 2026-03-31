# 🌆 Street Cloud: Real-Time Participatory Urban Design Tool

[![License: BSL-1.0](https://img.shields.io/badge/License-BSL_1.0-yellow.svg)](https://opensource.org/licenses/BSL-1.0)
[![Stack: Python + FastAPI](https://img.shields.io/badge/Stack-Python_%7C_FastAPI-blue.svg)](#-technical-architecture)
[![AI: SDXL Turbo (Local)](https://img.shields.io/badge/AI-SDXL_Turbo_(Local_GPU)-purple.svg)](#-setup-guide)
[![Engine: ComfyUI](https://img.shields.io/badge/Engine-ComfyUI-green.svg)](https://github.com/comfyanonymous/ComfyUI)
[![Realtime: WebSocket](https://img.shields.io/badge/Realtime-WebSocket-orange.svg)](#-architecture)

**Street Cloud** is a real-time participatory urban design tool built for planning workshops, urban futures congresses, and community engagement sessions. This open-source implementation runs **100% locally on your GPU** — zero API costs, zero cloud dependency, fully offline-capable.

Audience members submit words describing their ideal street redesign. The tool responds with a **live animated word cloud** and **AI-regenerated street imagery every 5 seconds**, powered by Stable Diffusion running on your own machine.

---

## 🎬 How It Works

```
Audience phones       →     Submit words      →    Your PC (FastAPI)
                                                          │
                                                    Word aggregation
                                                          │
                                              ┌───────────┴───────────┐
                                              │                       │
                                        Word Cloud              SDXL Turbo
                                        (D3.js live)         (ComfyUI local)
                                              │                       │
                                              └───────────┬───────────┘
                                                          │
                                               Presenter Screen
                                          (Word Cloud + Street Image)
                                              updates every 5 seconds
```

> The bigger the word in the cloud — the more people submitted it.
> The street image reflects the crowd's collective vision in real time.

---

## 💎 Feature Suite

### 🗣️ Live Participatory Input
- Mobile-friendly audience submission page — no app install needed
- Audience joins via any browser on the same Wi-Fi network
- Duplicate submission prevention with cooldown
- Live submission counter shown to all participants

### ☁️ Animated Word Cloud
- Real-time D3.js word cloud with smooth animations
- Word size proportional to submission frequency
- Colorful, high-contrast display optimised for projector screens
- Updates instantly on every new word submission

### 🖼️ AI Street Image Regeneration
- Automatically regenerates street imagery every **5 seconds**
- Powered by **SDXL Turbo** running locally on your GPU — no API fees
- Top 8 most-submitted words are used to build the generation prompt
- Smooth fade transition between image generations
- Graceful fallback to word-cloud-only mode if ComfyUI is offline

### 📡 Real-Time WebSocket Architecture
- Presenter and audience screens sync via WebSocket
- No page refresh needed — everything updates live
- Supports multiple simultaneous presenter screens
- Offline-capable once loaded (no internet dependency)

---

## 🛠️ Technical Architecture

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, FastAPI, Uvicorn |
| **Real-Time Sync** | WebSockets (native FastAPI) |
| **Word Storage** | In-memory Python dict (no database) |
| **Image Generation** | ComfyUI API → SDXL Turbo (local GPU) |
| **Word Cloud** | D3.js v7 + d3-cloud (CDN) |
| **Frontend** | Vanilla HTML, CSS, JavaScript |
| **GPU Target** | NVIDIA RTX series (8GB+ VRAM recommended) |

---

## 📁 Project Structure

```
street-cloud/
├── server.py                    # FastAPI app + WebSocket + 5s background loop
├── word_manager.py              # Thread-safe word frequency counter
├── prompt_builder.py            # Converts top words into SD image prompts
├── image_generator.py           # ComfyUI API client (local image generation)
├── comfyui_workflow.json        # SDXL Turbo txt2img workflow
├── comfyui_workflow_img2img.json # img2img variant workflow
├── requirements.txt             # Python dependencies
└── static/
    ├── presenter.html           # Full-screen presenter display
    ├── input.html               # Audience mobile submission page
    └── style.css                # Shared dark theme styles
```

---

## ⚙️ Setup Guide

### Prerequisites
- Windows 10/11 PC with NVIDIA GPU (8GB+ VRAM recommended)
- Python 3.10 or later
- Git installed

---

### Step 1 — Install ComfyUI

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt
```

---

### Step 2 — Download SDXL Turbo Model

Download the model and place it inside `ComfyUI/models/checkpoints/`:

**Direct link:**
```
https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors
```

**Or via terminal (wget):**
```bash
wget -P ComfyUI/models/checkpoints/ \
  "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors"
```

> ⚠️ File size is approximately 6.7 GB. Ensure you have sufficient disk space.

---

### Step 3 — Run ComfyUI

```bash
cd ComfyUI
python main.py --listen
```

ComfyUI will be available at `http://127.0.0.1:8188`.

> If ComfyUI is not running, Street Cloud automatically falls back to **word-cloud-only mode** — a grey placeholder image is shown instead of AI generations.

---

### Step 4 — Install Street Cloud Dependencies

```bash
cd /path/to/street-cloud
pip install -r requirements.txt
```

---

### Step 5 — Run Street Cloud

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## 🚀 Usage

| Screen | URL | Who Opens It |
|---|---|---|
| **Presenter** | `http://localhost:8000/presenter` | Facilitator / projector screen |
| **Audience Input** | `http://<YOUR_LOCAL_IP>:8000/input` | Audience phones via Wi-Fi |

### Finding Your Local IP Address

**Windows:**
```bash
ipconfig
```
Look for `IPv4 Address` under your Wi-Fi adapter (e.g., `192.168.1.42`).

**macOS / Linux:**
```bash
ip route get 1 | awk '{print $7}'
```

Share `http://192.168.1.42:8000/input` with your audience via a QR code or written on the board.

> 💡 **Tip:** Both your PC and audience devices must be on the **same Wi-Fi network**.

---

## ⚙️ Configuration

| Setting | File | Default |
|---|---|---|
| Image regeneration interval | `server.py` → `image_generation_loop` | `5 seconds` |
| ComfyUI server URL | `image_generator.py` → `COMFYUI_BASE` | `http://127.0.0.1:8188` |
| SD model filename | `comfyui_workflow.json` node `"1"` | `sd_xl_turbo_1.0_fp16.safetensors` |
| Output image size | `comfyui_workflow.json` node `"5"` | `832 × 512 px` |
| Words used in prompt | `server.py` → `word_texts` slice | Top `8` words |
| Words shown in cloud | `server.py` → `get_top_words` | Top `20` words |
| Generation steps | `comfyui_workflow.json` | `4` (SDXL Turbo optimised) |

---

## 🔧 Troubleshooting

**Grey placeholder shown instead of AI images**
- Confirm ComfyUI is running: open `http://127.0.0.1:8188` in your browser
- Check the Uvicorn terminal for `[ImageGenerator]` error messages
- Ensure the SDXL Turbo model file is inside `ComfyUI/models/checkpoints/`

**Audience devices cannot reach the input page**
- Ensure all devices are connected to the **same Wi-Fi network**
- Check Windows Firewall — allow inbound connections on port `8000`
- Confirm your local IP with `ipconfig` and share the correct address

**Word cloud not rendering**
- The presenter page loads D3.js from CDN — internet access is required the first time
- After first load, you may cache the JS files locally for offline use

**Image generation is slow**
- SDXL Turbo at 4 steps should generate in 3–8 seconds on RTX 8GB
- Reduce image resolution in `comfyui_workflow.json` if needed (try `640 × 384`)
- Close other GPU-intensive applications while running

---

## 📄 License

This project is licensed under the **BSL-1.0 License** — see the [LICENSE](LICENSE) file for full details.

---

## 🏛️ Affiliation

**SmartMind UI & AI Group | Urban Simulation Lab**
Department of Town & Country Planning
University of Moratuwa, Sri Lanka

Developed by **[Sandaruwan Sankalpa](https://github.com/sandaru01-IH)**
The Department of Town & Country Planning, University of Moratuwa, Sri Lanka

---
