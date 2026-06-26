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

## 🗣️ Thành phần 2: Máy chủ API tương thích OpenAI TTS

Giả lập chuẩn endpoint `/v1/audio/speech` của OpenAI để thay thế trực tiếp vào các hệ thống chat AI, trợ lý ảo.

### Các tính năng chính
*   **Edge-TTS miễn phí**: Dịch vụ giọng nói Microsoft Edge chất lượng cao, hoàn toàn miễn phí không cần API Key.
*   **ElevenLabs tích hợp**: Hỗ trợ giọng đọc cao cấp của ElevenLabs với cơ chế xoay vòng tài khoản/API key.
*   **SSE Streaming**: Truyền phát luồng âm thanh thời gian thực qua Server-Sent Events.

### Khởi chạy bằng Docker
```bash
docker run -d -p 5050:5050 travisvn/openai-edge-tts:latest
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

## 🗣️ Component 2: OpenAI-Compatible Edge-TTS API Server

A lightweight service that emulates the OpenAI TTS API (`/v1/audio/speech`) using the free Microsoft Edge TTS or ElevenLabs.

### Quick Start with Docker
```bash
docker run -d -p 5050:5050 travisvn/openai-edge-tts:latest
```
Access the server API at `http://localhost:5050/v1/audio/speech`.

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
