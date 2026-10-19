import os
import sys
from pathlib import Path

import requests


BASE_URL = os.getenv("TTS_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
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


def synthesize(text: str, api_key: str, voice: str = "zh-CN-YunxiNeural",
               speed: float = 1.0, pitch: float = 1.0,
               style: str = "general", volume: float = 1.0) -> bytes:
    headers = {"Content-Type": "application/json", "X-API-Key": api_key}

    response = requests.post(
        f"{BASE_URL}/tts",
        json={
            "text": text,
            "engine": "edge",
            "voice": voice,
            "format": "MP3",
            "speed": speed,
            "pitch": pitch,
            "style": style,
            "volume": volume,
        },
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

    # 验证 API Key
    resp = requests.get(
        f"{BASE_URL}/health",
        headers={"X-API-Key": api_key},
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"API Key 验证失败: {resp.status_code}")
        return

    print("API Key 验证通过。")
    print("Edge TTS client. Enter q to quit, s/v/p/o to adjust style/voice/pitch/volume.")
    print(f"  voice=zh-CN-YunxiNeural  style=general  speed=1.0  pitch=1.0  volume=1.0")

    voice = "zh-CN-YunxiNeural"
    style = "general"
    speed = 1.0
    pitch = 1.0
    volume = 1.0

    while True:
        text = input("> ").strip()
        if not text:
            continue
        if text.lower() == "q":
            return
        if text.lower() == "s":
            style = input("style (general/cheerful/sad/angry/...): ").strip() or "general"
            print(f"  style={style}")
            continue
        if text.lower() == "v":
            voice = input("voice: ").strip() or "zh-CN-YunxiNeural"
            print(f"  voice={voice}")
            continue
        if text.lower() == "p":
            pitch = float(input("pitch (1.0=正常, 1.2=提高20%): ").strip() or "1.0")
            print(f"  pitch={pitch}")
            continue
        if text.lower() == "o":
            speed = float(input("speed (0.5-2.0): ").strip() or "1.0")
            volume = float(input("volume (1.0=正常, 1.2=增强20%): ").strip() or "1.0")
            print(f"  speed={speed}  volume={volume}")
            continue

        try:
            audio = synthesize(text, api_key, voice, speed, pitch, style, volume)
        except RuntimeError as exc:
            print(f"Synthesis failed: {exc}")
            continue

        output = OUTPUT_DIR / "output_edge.mp3"
        output.write_bytes(audio)
        print(f"Saved output_edge.mp3: {len(audio)} bytes")


if __name__ == "__main__":
    main()
