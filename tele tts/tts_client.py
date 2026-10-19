import os
import sys
from pathlib import Path

import requests


BASE_URL = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUTPUT_DIR = Path(__file__).parent


def _read_key(prompt: str = "API Key: ") -> str:
    """Read API key with masked echo on Windows, fallback to plain input."""
    try:
        import msvcrt

        sys.stdout.write(prompt)
        sys.stdout.flush()
        chars = []
        while True:
            ch = msvcrt.getch()
            if ch in (b"\r", b"\n"):
                sys.stdout.write("\n")
                break
            elif ch == b"\x08":
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
            else:
                chars.append(ch.decode("utf-8", errors="ignore"))
                sys.stdout.write("*")
            sys.stdout.flush()
        return "".join(chars).strip()
    except (ImportError, AttributeError):
        return input(prompt).strip()


def synthesize(text: str, engine: str, api_key: str) -> bytes:
    headers = {"Content-Type": "application/json", "X-API-Key": api_key}

    response = requests.post(
        f"{BASE_URL}/tts",
        json={"text": text, "engine": engine},
        headers=headers,
        timeout=60,
    )
    if response.status_code != 200:
        try:
            raise RuntimeError(response.json())
        except ValueError:
            raise RuntimeError(response.text[:500]) from None
    return response.content


def main() -> None:
    api_key = os.getenv("TTS_API_KEY", "").strip()
    if not api_key:
        print("请输入启动服务时生成的 API Token：")
        api_key = _read_key()
        if not api_key:
            print("未输入 API Key，退出。")
            return

    # 验证 API Key 是否有效
    resp = requests.get(
        f"{BASE_URL}/health",
        headers={"X-API-Key": api_key},
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"API Key 验证失败: {resp.status_code}")
        return

    print("API Key 验证通过。")
    engine = "edge"
    print("Unified TTS client. Enter q to quit or e to switch engine.")

    while True:
        text = input("> ").strip()
        if not text:
            continue
        if text.lower() == "q":
            return
        if text.lower() == "e":
            engine = "supernatural" if engine == "edge" else "edge"
            print(f"Engine: {engine}")
            continue

        try:
            audio = synthesize(text, engine, api_key)
        except RuntimeError as exc:
            print(f"Synthesis failed: {exc}")
            continue

        extension = "mp3" if engine == "edge" else "wav"
        output = OUTPUT_DIR / f"output_{engine}.{extension}"
        output.write_bytes(audio)
        print(f"Saved {output.name}: {len(audio)} bytes")


if __name__ == "__main__":
    main()
