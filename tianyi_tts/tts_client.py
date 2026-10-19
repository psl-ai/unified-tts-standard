import os
import sys
from pathlib import Path

import requests


BASE_URL = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUTPUT_DIR = Path(__file__).parent


def _read_key(prompt: str = "API Key: ") -> str:
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


def main() -> None:
    api_key = os.getenv("TTS_API_KEY", "").strip()
    if not api_key:
        print("请输入 API Key（默认 my-fixed-key-2026）：")
        api_key = _read_key()
        if not api_key:
            api_key = "my-fixed-key-2026"

    # 验证
    resp = requests.get(
        f"{BASE_URL}/health",
        headers={"X-API-Key": api_key},
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"API Key 验证失败: {resp.status_code}")
        return

    print("API Key 验证通过。")
    engine = "supernatural"
    print(f"Tianyi TTS client. Engine: {engine}  Enter q to quit, e to switch engine.")

    while True:
        text = input("> ").strip()
        if not text:
            continue
        if text.lower() == "q":
            return
        if text.lower() == "e":
            engines = ["supernatural", "realtime", "offline"]
            idx = engines.index(engine)
            engine = engines[(idx + 1) % len(engines)]
            print(f"Engine: {engine}")
            continue

        try:
            r = requests.post(
                f"{BASE_URL}/tts/{engine}",
                json={"text": text, "voice": "xianliaonv"},
                headers={"X-API-Key": api_key},
                timeout=120,
            )
        except Exception as exc:
            print(f"Request failed: {exc}")
            continue

        if r.status_code != 200:
            try:
                print(f"Failed: {r.json()}")
            except ValueError:
                print(f"Failed: {r.text[:500]}")
            continue

        ext = "mp3"
        output = OUTPUT_DIR / f"output_tianyi.{ext}"
        output.write_bytes(r.content)
        print(f"Saved {output.name}: {len(r.content)} bytes")


if __name__ == "__main__":
    main()
