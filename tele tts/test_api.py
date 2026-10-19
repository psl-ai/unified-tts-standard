import os
from pathlib import Path

import requests


BASE_URL = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("TTS_API_KEY", "").strip()
OUTPUT_DIR = Path(__file__).parent


def headers() -> dict:
    result = {"Content-Type": "application/json"}
    if API_KEY:
        result["X-API-Key"] = API_KEY
    return result


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
        json={"engine": "edge"},
        headers=headers(),
        timeout=10,
    )
    passed += check("POST /tts validation", invalid, 422)

    synthesis = requests.post(
        f"{BASE_URL}/tts/edge",
        json={
            "text": "你好世界，欢迎使用统一 TTS 服务。",
            "format": "MP3",
            "speed": 1.0,
            "pitch": 1.0,
            "volume": 1.0,
        },
        headers=headers(),
        timeout=60,
    )
    passed += check("POST /tts/edge synthesis", synthesis, 200)
    if synthesis.status_code == 200:
        output = OUTPUT_DIR / "test_unified.mp3"
        output.write_bytes(synthesis.content)
        print(f"Saved test_unified.mp3: {len(synthesis.content)} bytes")

    # 引擎直连路由 + 参数校验
    invalid_rate = requests.post(
        f"{BASE_URL}/tts/edge",
        json={"text": "hello", "sample_rate": 99999},
        headers=headers(),
        timeout=10,
    )
    passed += check("POST /tts/edge invalid sample_rate", invalid_rate, 422)

    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
