import os
from pathlib import Path

import requests


BASE_URL = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
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
    total = 5

    health = requests.get(f"{BASE_URL}/health", headers=headers(), timeout=10)
    passed += check("GET /health", health, 200)

    # 缺少 text
    invalid = requests.post(
        f"{BASE_URL}/tts",
        json={"engine": "edge"},
        headers=headers(),
        timeout=10,
    )
    passed += check("POST /tts missing text", invalid, 422)

    # 非法 format
    invalid_fmt = requests.post(
        f"{BASE_URL}/tts/edge",
        json={"text": "hello", "format": "WAV"},
        headers=headers(),
        timeout=10,
    )
    passed += check("POST /tts/edge invalid format", invalid_fmt, 422)

    # Edge 合成（引擎直连路由）
    synthesis = requests.post(
        f"{BASE_URL}/tts/edge",
        json={
            "text": "你好世界，欢迎使用Edge TTS服务。",
            "speed": 1.0,
            "pitch": 1.0,
            "volume": 1.0,
        },
        headers=headers(),
        timeout=60,
    )
    passed += check("POST /tts/edge synthesis", synthesis, 200)
    if synthesis.status_code == 200:
        output = OUTPUT_DIR / "test_edge.mp3"
        output.write_bytes(synthesis.content)
        print(f"Saved test_edge.mp3: {len(synthesis.content)} bytes")

    # /text/ 兼容端点
    legacy = requests.post(
        f"{BASE_URL}/text/",
        json={"text": "兼容性测试", "engine": "edge"},
        headers=headers(),
        timeout=60,
    )
    passed += check("POST /text/ legacy", legacy, 200)

    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
