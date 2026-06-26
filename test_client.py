import requests
import json
import os
from dotenv import load_dotenv

# Load env file
load_dotenv()

PORT = int(os.getenv('PORT', '5050'))
API_KEY = os.getenv('API_KEY', 'your_api_key_here')
BASE_URL = f"http://localhost:{PORT}/v1"

print(f"--- Đang kết nối tới server tại {BASE_URL} ---")

# 1. Test model listing
try:
    print("\n1. Đang kiểm tra danh sách model (/v1/models)...")
    response = requests.get(f"{BASE_URL}/models")
    if response.status_code == 200:
        print("Thành công! Danh sách các model hỗ trợ:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Lỗi: HTTP {response.status_code} - {response.text}")
except Exception as e:
    print(f"Không thể kết nối tới server: {e}")
    exit(1)

# 2. Test TTS generation (Vietnamese)
try:
    print("\n2. Đang sinh giọng đọc tiếng Việt (/v1/audio/speech)...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": "tts-1",
        "input": "Xin chào! Tôi là giọng đọc tiếng Việt được sinh ra bởi Microsoft Edge TTS thông qua API tương thích OpenAI.",
        "voice": "vi-VN-HoaiMyNeural",  # Giọng nữ tiếng Việt chất lượng tốt
        "response_format": "mp3",
        "speed": 1.0
    }
    
    response = requests.post(f"{BASE_URL}/audio/speech", headers=headers, json=payload)
    
    if response.status_code == 200:
        output_file = "test_speech.mp3"
        with open(output_file, "wb") as f:
            f.write(response.content)
        print(f"Thành công! File âm thanh đã được lưu tại: {os.path.abspath(output_file)}")
        print(f"Kích thước file: {len(response.content)} bytes")
    else:
        print(f"Lỗi: HTTP {response.status_code} - {response.text}")
except Exception as e:
    print(f"Có lỗi xảy ra trong quá trình sinh âm thanh: {e}")
