import os
from pathlib import Path

import requests


BASE_URL = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("TTS_API_KEY", "my-fixed-key-2026").strip()
OUTPUT_DIR = Path(__file__).parent


def headers() -> dict:
    return {"Content-Type": "application/json", "X-API-Key": API_KEY}


def check(name: str, response: requests.Response, expected_status: int) -> bool:
    passed = response.status_code == expected_status
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}: expected {expected_status}, got {response.status_code}")
    if not passed:
        try:
            print(response.json())
        except ValueError:
            print(response.text[:500])
    return passed


def main() -> int:
    passed = 0
    total = 4

    health = requests.get(f"{BASE_URL}/health", headers=headers(), timeout=10)
    passed += check("GET /health", health, 200)

    invalid = requests.post(
        f"{BASE_URL}/tts",
        json={"engine": "supernatural"},
        headers=headers(),
        timeout=10,
    )
    passed += check("POST /tts validation (missing text)", invalid, 422)

    synthesis = requests.post(
        f"{BASE_URL}/tts/supernatural",
        json={
            "text": "你好世界，欢迎使用天翼TTS服务。",
            "voice": "xianliaonv",
            "format": "MP3",
            "speed": 1.0,
            "pitch": 1.0,
            "volume": 1.0,
        },
        headers=headers(),
        timeout=120,
    )
    passed += check("POST /tts/supernatural synthesis", synthesis, 200)
    if synthesis.status_code == 200:
        output = OUTPUT_DIR / "test_tianyi.mp3"
        output.write_bytes(synthesis.content)
        print(f"Saved test_tianyi.mp3: {len(synthesis.content)} bytes")

    passed += check("POST /tts/supernatural audio not empty", len(synthesis.content) > 0)

    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
