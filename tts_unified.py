"""
TTS 统一调用接口

一行代码调用任意 TTS 服务：

    from tts_unified import tts
    tts("你好世界")                        # 默认 Edge TTS
    tts("你好", engine="supernatural")     # 超自然语音
    tts("你好", service="tianyi")          # 天翼 TTS

支持的服务:
    teleai  → 端口 8000 (edge/supernatural/realtime/offline)
    edge    → 端口 8001 (edge)
    sherpa  → 端口 8002 (sherpa/offline)
    tianyi  → 端口 8900 (supernatural/realtime/offline)

环境变量:
    TTS_KEY  — API Key，默认 my-fixed-key-2026
"""

import os
from typing import Optional

import requests

KEY = os.getenv("TTS_KEY", "my-fixed-key-2026").strip()

SERVICES = {
    "teleai": "http://127.0.0.1:8000",
    "edge":   "http://127.0.0.1:8001",
    "sherpa": "http://127.0.0.1:8002",
    "tianyi": "http://127.0.0.1:8900",
}


def tts(
    text: str,
    engine: str = "edge",
    service: str = "edge",
    voice: Optional[str] = None,
    speed: float = 1.0,
    pitch: float = 1.0,
    volume: float = 1.0,
    style: str = "general",
    format: str = "WAV",
    sample_rate: Optional[int] = 16000,
    req_id: Optional[str] = None,
    extra_params: Optional[dict] = None,
    output: Optional[str] = None,
) -> Optional[bytes]:
    """
    统一 TTS 合成接口。

    参数:
        text:        待合成文本（必填）
        engine:      引擎名称，默认 edge
        service:     服务名称，可选 teleai/edge/sherpa/tianyi
        voice:       语音角色
        speed:       语速，1.0 正常
        pitch:       音调，1.0 正常
        volume:      音量，1.0 正常
        style:       语音风格
        format:      输出格式，MP3/WAV/FLAC
        sample_rate: 采样率
        req_id:      请求追踪 ID
        extra_params: 额外参数
        output:      保存路径，不传则只返回 bytes

    返回:
        bytes: 音频数据，失败返回 None
    """
    url = SERVICES.get(service)
    if not url:
        print(f"未知服务: {service}，可选: {list(SERVICES.keys())}")
        return None

    body = {"text": text, "engine": engine, "speed": speed, "pitch": pitch,
            "volume": volume, "style": style, "format": format}
    if voice:
        body["voice"] = voice
    if sample_rate is not None:
        body["sample_rate"] = sample_rate
    if req_id:
        body["req_id"] = req_id
    if extra_params:
        body["extra_params"] = extra_params

    try:
        r = requests.post(
            f"{url}/tts/{engine}",
            json=body,
            headers={"X-API-Key": KEY},
            timeout=120,
        )
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

    if r.status_code != 200:
        try:
            print(f"合成失败: {r.json()}")
        except ValueError:
            print(f"合成失败: HTTP {r.status_code}")
        return None

    if output:
        with open(output, "wb") as f:
            f.write(r.content)
        print(f"已保存: {output} ({len(r.content)} bytes)")

    return r.content


# ============ 命令行 ============
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python tts_unified.py <文本> [--engine edge] [--service edge] [--output out.mp3]")
        print()
        print("示例:")
        print('  python tts_unified.py "你好世界"')
        print('  python tts_unified.py "你好" --engine supernatural --service tianyi')
        print('  python tts_unified.py "你好" --speed 1.5 --volume 0.8')
        sys.exit(0)

    text = sys.argv[1]
    kwargs = {"text": text}

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--engine":
            kwargs["engine"] = sys.argv[i + 1]
        elif sys.argv[i] == "--service":
            kwargs["service"] = sys.argv[i + 1]
        elif sys.argv[i] == "--voice":
            kwargs["voice"] = sys.argv[i + 1]
        elif sys.argv[i] == "--speed":
            kwargs["speed"] = float(sys.argv[i + 1])
        elif sys.argv[i] == "--pitch":
            kwargs["pitch"] = float(sys.argv[i + 1])
        elif sys.argv[i] == "--volume":
            kwargs["volume"] = float(sys.argv[i + 1])
        elif sys.argv[i] == "--style":
            kwargs["style"] = sys.argv[i + 1]
        elif sys.argv[i] == "--format":
            kwargs["format"] = sys.argv[i + 1]
        elif sys.argv[i] == "--sample_rate":
            kwargs["sample_rate"] = int(sys.argv[i + 1])
        elif sys.argv[i] == "--output":
            kwargs["output"] = sys.argv[i + 1]
        i += 2

    tts(**kwargs)
