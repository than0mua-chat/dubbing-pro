# AI Subtitles & Voice Synthesis Studio (Dubbing Pro) 🗣️📺

[![GitHub stars](https://img.shields.io/github/stars/than0mua-chat/dubbing-pro?style=social)](https://github.com/than0mua-chat/dubbing-pro)
[![GitHub forks](https://img.shields.io/github/than0mua-chat/dubbing-pro?style=social)](https://github.com/than0mua-chat/dubbing-pro)

[**[English Version below]**](#english-version)

---

# BẢN TIẾNG VIỆT (VIETNAMESE VERSION)

Bộ công cụ thương mại chuyên nghiệp phục vụ thuyết minh tự động (Dubbing), tải phụ đề YouTube chất lượng cao, chuyển đổi văn bản thành giọng nói (TTS) tốc độ cao, hoạt động hoàn toàn trực tiếp trên máy tính cá nhân dưới dạng ứng dụng Desktop GUI Studio.

---

## 📺 Ứng dụng Desktop GUI Studio (Dubbing Pro)

Giao diện đồ họa chuyên nghiệp và trực quan giúp tối ưu hóa quy trình thuyết minh video từ chuẩn bị phụ đề đến xuất bản sản phẩm hoàn chỉnh.

### Các tính năng chính
*   **📥 Tải phụ đề YouTube thông minh**:
    *   Tự động trích xuất Video ID từ mọi dạng link YouTube (watch, shorts, embed, share).
    *   Tải danh sách phụ đề (cả thủ công và tự động) qua Proxy Pool để tránh bị chặn IP từ YouTube.
    *   **Google Translate theo lô (Batch)**: Tự động tải bản gốc (ví dụ: English) và dịch chất lượng cao qua Google Translate theo từng cụm dưới 3000 ký tự. Loại bỏ hoàn toàn lỗi dịch thiếu hoặc trộn tiếng Anh của YouTube.
*   **🗣️ Thuật toán ghép nối âm thanh chuyên nghiệp**:
    *   **Khớp Timeline video**: Tự động chèn khoảng lặng (silence) để âm thanh khớp chuẩn xác với thời gian gốc của phụ đề trong video.
    *   **Bù khoảng lặng ở cuối (End-Silence Padding)**: Tự động tính toán chênh lệch và chèn thêm khoảng lặng ở cuối file âm thanh nếu câu cuối cùng kết thúc sớm, giúp âm thanh và phụ đề khớp 100% thời lượng với video gốc.
    *   **Ngắt nghỉ theo ngữ cảnh**: Tự động phát hiện dấu câu (dấu `,` ngắt nghỉ ngắn, dấu `.!?` nghỉ dài) và tự động xử lý viết hoa/viết thường để tạo khoảng lặng thở tự nhiên.
    *   **Quản lý từ viết tắt (Acronym Processing)**: Tự động phát hiện và chuyển đổi từ viết tắt tiếng Việt sang dạng mô tả/đọc đầy đủ.
*   **🎬 Ghép nối trực tiếp vào Video (FFmpeg)**:
    *   Mux trực tiếp luồng âm thanh đã căn chỉnh và file phụ đề `.srt` vào video gốc chỉ bằng 1 cú nhấp chuột qua thư viện FFmpeg đi kèm.

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
Để đóng gói toàn bộ ứng dụng (bao gồm giao diện và thuật toán xử lý âm thanh) thành file chạy độc lập `.exe` trên Windows:
*   Chạy tệp **`build_exe.bat`**.
*   Thư mục đóng gói sẽ được tạo ra tại **`dist\DubbingPro`**.
*   Người dùng chỉ cần chạy tệp **`dist\DubbingPro\DubbingPro.exe`** mà không cần cài đặt Python hay bất kỳ thư viện nào khác trên máy.

---

# ENGLISH VERSION

A professional desktop software suite designed for automatic video dubbing, YouTube subtitle downloading, and high-speed text-to-speech (TTS) synthesis.

---

## 📺 Desktop GUI Studio (Dubbing Pro)

An advanced graphical interface designed to simplify the workflow of dubbing videos, downloading transcripts, and synthesizing audio tracks.

### Key Features
*   **📥 YouTube Subtitle Downloader**:
    *   Extracts Video ID from any YouTube URL and fetches manual/auto-generated transcripts.
    *   Supports Proxy Pool configurations to prevent IP blocks from YouTube.
    *   **High-Fidelity Google Translation**: Bypasses YouTube's machine translator by downloading the original transcript and batch-translating it via Google Translate.
*   **🗣️ Professional Audio Merger**:
    *   **Timeline Alignment**: Inserts precise silence blocks to align the voice output with original video timestamps.
    *   **End-Silence Padding**: Appends trailing silence to match the original video duration 100%, preventing early cut-offs.
    *   **Context-Aware Pauses**: Analyzes text casing and punctuation (mild marks like `,` vs. sentence enders like `.` or `?`) to determine natural breathing pauses.
    *   **Acronym Processing**: Automatically normalizes and expands Vietnamese acronyms to their full pronunciation format.
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

## 🤝 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
