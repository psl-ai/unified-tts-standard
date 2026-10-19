import os
from pathlib import Path

import requests


BASE_URL = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
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
    total = 6

    health = requests.get(f"{BASE_URL}/health", headers=headers(), timeout=10)
    passed += check("GET /health", health, 200)

    # 缺少 text
    invalid = requests.post(
        f"{BASE_URL}/tts",
        json={"engine": "sherpa"},
        headers=headers(),
        timeout=10,
    )
    passed += check("POST /tts missing text", invalid, 422)

    # 非法 engine
    invalid_eng = requests.post(
        f"{BASE_URL}/tts",
        json={"text": "hello", "engine": "invalid"},
        headers=headers(),
        timeout=10,
    )
    passed += check("POST /tts invalid engine", invalid_eng, 422)

    # Sherpa 合成（顶层 speed）
    synthesis = requests.post(
        f"{BASE_URL}/tts/sherpa",
        json={
            "text": "你好世界，欢迎使用Sherpa TTS服务。",
            "voice": "0",
            "speed": 1.0,
        },
        headers=headers(),
        timeout=120,
    )
    passed += check("POST /tts/sherpa synthesis", synthesis, 200)
    if synthesis.status_code == 200:
        output = OUTPUT_DIR / "test_sherpa.wav"
        output.write_bytes(synthesis.content)
        print(f"Saved test_sherpa.wav: {len(synthesis.content)} bytes")

    # 向后兼容 - extra_params.speed
    compat = requests.post(
        f"{BASE_URL}/tts/sherpa",
        json={
            "text": "向后兼容测试。",
            "voice": "0",
            "extra_params": {"speed": 1.0},
        },
        headers=headers(),
        timeout=120,
    )
    passed += check("POST /tts/sherpa extra_params.speed", compat, 200)
    if compat.status_code == 200:
        output = OUTPUT_DIR / "test_sherpa_compat.wav"
        output.write_bytes(compat.content)
        print(f"Saved test_sherpa_compat.wav: {len(compat.content)} bytes")

    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
