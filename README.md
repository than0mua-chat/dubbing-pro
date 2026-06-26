# AI Subtitles & Voice Synthesis Studio (Dubbing Pro) & OpenAI Edge-TTS API 🗣️📺

[![GitHub stars](https://img.shields.io/github/stars/travisvn/openai-edge-tts?style=social)](https://github.com/travisvn/openai-edge-tts)
[![GitHub forks](https://img.shields.io/github/forks/travisvn/openai-edge-tts?style=social)](https://github.com/travisvn/openai-edge-tts)
[![Discord](https://img.shields.io/badge/Discord-Voice_AI_%26_TTS_Tools-blue?logo=discord&logoColor=white)](https://discord.gg/GkFbBCBqJ6)

A comprehensive, commercial-grade suite for automatic video dubbing, subtitle download, high-speed text-to-speech (TTS) synthesis, and local OpenAI-compatible voice services.

This repository contains two main components:
1. **Desktop GUI Application (`app_gui.py`)**: A professional studio interface for downloading subtitles from YouTube, translating them, generating high-speed concurrent TTS audio, and merging audio back into video.
2. **OpenAI-Compatible Edge-TTS API Server (`app/server.py`)**: A lightweight Python server that emulates the OpenAI TTS API (`/v1/audio/speech`) using the free Microsoft Edge TTS or ElevenLabs engines.

---

## 📺 Component 1: Desktop GUI Studio (Dubbing Pro)

An advanced graphical interface designed to simplify the workflow of dubbing videos, translating transcripts, and synthesizing audio.

### Key Features
*   **📥 YouTube Subtitle Downloader**:
    *   Automatic Video ID extraction from any YouTube URL (Watch, Shorts, Embed, Share links).
    *   Scrapes manual and auto-generated transcripts with automatic proxy pool routing.
    *   **High-Fidelity Google Translation**: Bypasses YouTube's buggy machine translator by downloading the original transcript and batch-translating it via Google Translate. This prevents mixed-language output (half-English, half-Vietnamese).
*   **⚡ Concurrency & Proxy Pool**:
    *   Supports multithreaded processing for ElevenLabs and asyncio batch processing for Edge-TTS.
    *   Integrated Proxy Pool manager that rotates active proxies and automatically retries failed network requests up to 3 times to prevent IP bans.
*   **🗣️ Professional Audio Merger**:
    *   **Timeline Alignment**: Inserts precise silence blocks to align the voice output with original video timestamps.
    *   **End-Silence Padding**: Automatically calculates the duration difference between synthesized audio and the original subtitle track, appending trailing silence to match the video duration 100% (fixing early cut-offs).
    *   **Context-Aware Pauses**: Analyzes text casing and punctuation (mild marks like `,` vs. sentence enders like `.` or `?`) to determine natural breathing pauses.
*   **🎬 FFmpeg Video Muxer**:
    *   Merges the final aligned audio track and subtitles directly back into the original video with a single click.

### Getting Started with the GUI

#### Prerequisites
Make sure you have Python 3.9+ and FFmpeg installed on your system.
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the desktop studio:
   ```bash
   python app_gui.py
   ```
   *(Or run `run_app.bat` on Windows)*

---

## 🗣️ Component 2: OpenAI-Compatible Edge-TTS API Server

A lightweight service that emulates the OpenAI TTS API (`/v1/audio/speech`) using the free Microsoft Edge TTS engine (online, no subscription required) and ElevenLabs. It is highly suited as a drop-in replacement for tools like Open WebUI, AnythingLLM, etc.

### Features
*   **OpenAI Compatibility**: Standard request structure supporting voice mapping and playback speed adjustments.
*   **SSE Streaming**: Real-time audio streaming via Server-Sent Events (`stream_format: "sse"`).
*   **Flexible Formats**: Supports `mp3`, `opus`, `aac`, `flac`, `wav`, and `pcm`.

### Quick Start with Docker
The simplest way to spin up the API server:
```bash
docker run -d -p 5050:5050 travisvn/openai-edge-tts:latest
```
Access the server API at `http://localhost:5050/v1/audio/speech`.

---

## ⚙️ Configuration (.env)

Create a `.env` file in the root directory to customize the API server and GUI default behaviors:

```ini
API_KEY=your_api_key_here
PORT=5050
REQUIRE_API_KEY=False

# Default TTS configurations
DEFAULT_VOICE=vi-VN-HoaiAnNeural
DEFAULT_RESPONSE_FORMAT=mp3
DEFAULT_SPEED=1.0
DEFAULT_LANGUAGE=vi-VN

# Features activation
REMOVE_FILTER=False
EXPAND_API=True
DETAILED_ERROR_LOGGING=True
```

---

## 🛠️ Verification & Development

To compile and verify the GUI code without running it:
```bash
python -m py_compile app_gui.py
```

### API Endpoint Test Example
You can send a standard OpenAI payload to test the local server:
```bash
curl http://localhost:5050/v1/audio/speech \
  -H "Authorization: Bearer your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "Xin chào! Đây là bản thuyết minh tự động từ hệ thống Dubbing Pro.",
    "voice": "vi-VN-NamMinhNeural"
  }' \
  --output test_output.mp3
```

---

## 🤝 Contribution & License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. 

If you find this project helpful, please give it a **⭐️ Star** on GitHub!
