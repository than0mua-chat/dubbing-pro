# AI Subtitles & Voice Synthesis Studio (Dubbing Pro) & OpenAI Edge-TTS API 🗣️📺

[![GitHub stars](https://img.shields.io/github/stars/than0mua-chat/dubbing-pro?style=social)](https://github.com/than0mua-chat/dubbing-pro)
[![GitHub forks](https://img.shields.io/github/than0mua-chat/dubbing-pro?style=social)](https://github.com/than0mua-chat/dubbing-pro)

[**[English Version below]**](#english-version)

---

# BẢN TIẾNG VIỆT (VIETNAMESE VERSION)

Bộ công cụ thương mại chuyên nghiệp phục vụ thuyết minh tự động (Dubbing), tải phụ đề YouTube chất lượng cao, chuyển đổi văn bản thành giọng nói (TTS) tốc độ cao và cung cấp máy chủ dịch vụ giọng nói tương thích OpenAI API.

Dự án gồm 2 thành phần cốt lõi:
1. **Desktop GUI Studio (`app_gui.py`)**: Giao diện máy tính chuyên nghiệp để biên tập phụ đề, tải & dịch phụ đề YouTube, gọi TTS đa luồng và đồng bộ ghép âm thanh/phụ đề vào video gốc.
2. **OpenAI-Compatible Edge-TTS API Server (`app/server.py`)**: Máy chủ API giả lập OpenAI TTS (`/v1/audio/speech`) để các ứng dụng bên thứ ba (như Open WebUI, AnythingLLM,...) kết nối và sử dụng giọng đọc Edge-TTS hoặc ElevenLabs.

---

## 📺 Thành phần 1: Ứng dụng Desktop GUI Studio (Dubbing Pro)

Giao diện đồ họa tối ưu hóa quy trình làm việc từ việc chuẩn bị văn bản đến khi xuất bản video thuyết minh hoàn chỉnh.

### Các tính năng chính
*   **📥 Tải phụ đề YouTube thông minh**:
    *   Tự động trích xuất Video ID từ mọi dạng link YouTube (watch, shorts, embed, share).
    *   Tải danh sách phụ đề (cả thủ công và tự động) qua Proxy Pool để tránh bị chặn IP.
    *   **Google Translate theo lô (Batch)**: Tự động tải bản gốc (English) và dịch chất lượng cao qua Google Translate theo từng cụm dưới 3000 ký tự. Loại bỏ hoàn toàn lỗi dịch thiếu/trộn tiếng Anh của YouTube.
*   **🗣️ Thuật toán ghép nối âm thanh chuyên nghiệp**:
    *   **Khớp Timeline video**: Tự động chèn khoảng lặng (silence) để âm thanh khớp chuẩn xác với thời gian gốc của phụ đề trong video.
    *   **Bù khoảng lặng ở cuối (End-Silence Padding)**: Tự động tính toán chênh lệch và chèn thêm khoảng lặng ở cuối file âm thanh nếu câu cuối cùng bị lỗi hoặc kết thúc sớm, giúp âm thanh và phụ đề khớp 100% thời lượng với video gốc.
    *   **Ngắt nghỉ theo ngữ cảnh**: Tự động phát hiện dấu câu (dấu `,` ngắt nghỉ ngắn, dấu `.!?` nghỉ dài) và viết hoa/thường để tạo khoảng lặng thở tự nhiên.
*   **🎬 Ghép nối trực tiếp vào Video (FFmpeg)**:
    *   Mux trực tiếp luồng âm thanh đã căn chỉnh và file phụ đề `.srt` vào video gốc chỉ bằng 1 cú nhấp chuột.

### Hướng dẫn sử dụng & Chạy ứng dụng
1.  **Cài đặt thư viện cần thiết**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Khởi chạy giao diện**:
    Double-click vào tệp **`run_app.bat`** hoặc chạy lệnh:
    ```bash
    python app_gui.py
    ```

### 📦 Hướng dẫn đóng gói ứng dụng (Deploy Standalone)
Để đóng gói toàn bộ ứng dụng (bao gồm giao diện, thuật toán xử lý âm thanh và máy chủ API nền) thành file chạy độc lập `.exe` trên Windows:
*   Chạy tệp **`build_exe.bat`**.
*   Thư mục đóng gói sẽ được tạo ra tại **`dist\DubbingPro`**.
*   Người dùng chỉ cần chạy tệp **`dist\DubbingPro\DubbingPro.exe`** mà không cần cài đặt Python hoặc bất kỳ thư viện nào khác trên máy.

---

## 🗣️ Thành phần 2: Máy chủ Giả lập Đa API (Multi-API Emulation Backend)

Máy chủ dịch vụ trung gian chạy ngầm (mặc định trên cổng `5050`), cung cấp các cổng kết nối API chuẩn hóa, cho phép các ứng dụng bên thứ ba dễ dàng cấu hình và sử dụng công nghệ chuyển giọng nói miễn phí.

### Các tính năng chính của Backend:
*   **Giả lập OpenAI Speech API (`/v1/audio/speech`)**: Đóng vai trò như một drop-in replacement hoàn hảo cho OpenAI TTS, tương thích tốt với Open WebUI, AnythingLLM, và các nền tảng AI.
*   **Giả lập ElevenLabs API (`/elevenlabs/v1/text-to-speech/<voice_id>`)**: Cho phép các phần mềm/ứng dụng chỉ hỗ trợ ElevenLabs có thể trỏ về địa chỉ local này để chuyển đổi text sang giọng đọc Edge-TTS hoàn toàn miễn phí.
*   **Giả lập Microsoft Azure Speech API (`/azure/cognitiveservices/v1`)**: Biên dịch các yêu cầu chuẩn SSML của Azure sang giọng đọc Edge-TTS.
*   **Xoay vòng và Xử lý ElevenLabs**: Quản lý pool API keys ElevenLabs nâng cao, hỗ trợ tự động xoay vòng tài khoản.
*   **Truyền phát Luồng âm thanh (SSE Streaming)**: Hỗ trợ truyền phát âm thanh thời gian thực qua cơ chế Server-Sent Events (`stream_format: "sse"`).
*   **Bộ lọc Chuẩn hóa Văn bản**: Tiền xử lý văn bản đầu vào (loại bỏ biểu tượng cảm xúc, dọn dẹp cấu trúc Markdown, chuyển đổi tiêu đề thành giọng văn mô tả, lọc ký tự đặc biệt).
*   **Cung cấp dữ liệu cho GUI**: Endpoint `/v1/voices/all` chịu trách nhiệm cung cấp danh sách giọng đọc và cấu hình cho giao diện Desktop chính.

### Cách khởi chạy độc lập
*   **Sử dụng Docker**:
    ```bash
    docker run -d -p 5050:5050 travisvn/openai-edge-tts:latest
    ```
*   **Chạy trực tiếp bằng Python**:
    ```bash
    set PYTHONPATH=app
    python app/server.py
    ```

---

# ENGLISH VERSION

A commercial-grade suite for automatic video dubbing, subtitle downloads, high-speed TTS synthesis, and local OpenAI-compatible voice services.

---

## 📺 Component 1: Desktop GUI Studio (Dubbing Pro)

An advanced graphical interface designed to simplify the workflow of dubbing videos, translating transcripts, and synthesizing audio.

### Key Features
*   **📥 YouTube Subtitle Downloader**:
    *   Extracts Video ID from any YouTube URL and fetches manual/auto-generated transcripts.
    *   **High-Fidelity Google Translation**: Bypasses YouTube's buggy machine translator by downloading the original transcript and batch-translating it via Google Translate.
*   **🗣️ Professional Audio Merger**:
    *   **Timeline Alignment**: Inserts precise silence blocks to align the voice output with original video timestamps.
    *   **End-Silence Padding**: Appends trailing silence to match the original video duration 100%, preventing early cut-offs.
    *   **Context-Aware Pauses**: Analyzes text casing and punctuation (mild marks like `,` vs. sentence enders like `.` or `?`) to determine natural breathing pauses.
*   **🎬 FFmpeg Video Muxer**:
    *   Merges the final aligned audio track and subtitles directly back into the original video.

### Running & Packaging the GUI

1.  **Run Locally**:
    ```bash
    pip install -r requirements.txt
    python app_gui.py
    ```
    *(Or run `run_app.bat` on Windows)*

2.  **📦 Standalone Packaging (PyInstaller)**:
    *   Run **`build_exe.bat`** on Windows.
    *   The compiled standalone app will be created in **`dist\DubbingPro`**.
    *   Users can launch the studio via **`dist\DubbingPro\DubbingPro.exe`** without Python.

---

## 🗣️ Component 2: Multi-API Emulation Backend Server

A lightweight, local proxy server running on port `5050` by default. It emulates multiple commercial TTS endpoints, enabling client software to use free Edge-TTS or proxy ElevenLabs.

### Core Backend Features:
*   **OpenAI TTS API Emulation (`/v1/audio/speech`)**: Drop-in replacement for OpenAI's speech endpoint, fully compatible with Open WebUI, AnythingLLM, and other AI frameworks.
*   **ElevenLabs API Emulation (`/elevenlabs/v1/text-to-speech/<voice_id>`)**: Translates ElevenLabs-style requests into free Microsoft Edge-TTS audio. Useful for applications that hardcode ElevenLabs support.
*   **Azure Speech API Emulation (`/azure/cognitiveservices/v1`)**: Parses Azure SSML documents and synthesizes speech using the local Edge-TTS engine.
*   **SSE Streaming Support**: Real-time audio streaming via Server-Sent Events.
*   **Text Preprocessing Pipeline**: Automatically strips Markdown syntax, removes emojis, announces headers, and normalizes line breaks before rendering speech.
*   **GUI Controller Endpoint**: Exposes `/v1/voices/all` which dynamically provides voice listings and features configurations to the desktop GUI.

### How to Run Independently
*   **With Docker**:
    ```bash
    docker run -d -p 5050:5050 travisvn/openai-edge-tts:latest
    ```
*   **With Python**:
    ```bash
    set PYTHONPATH=app
    python app/server.py
    ```

---

## ⚙️ Configuration (.env)

Create a `.env` file in the root directory to customize default behaviors:

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

## 🤝 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
