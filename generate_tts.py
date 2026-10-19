"""生成 TTS 语音文件"""

import requests

# 配置
URL  = "http://127.0.0.1:9000"       # Gateway 地址
KEY  = "my-fixed-key-2026"            # API Key
TEXT = "这里是中电信数智，有什么可以帮您的"

# 参数
params = {
    "text":        TEXT,
    "engine":      "supernatural",
    "voice":       "xianliaonv",
    "format":      "WAV",
    "sample_rate": 16000,
    "speed":       1.0,
    "pitch":       1.0,
    "volume":      1.0,
}

# 发送请求
r = requests.post(
    f"{URL}/tts/supernatural",
    json=params,
    headers={"X-API-Key": KEY},
    timeout=120,
)

# 保存
if r.status_code == 200:
    output = "D:/tts统一标准/tts/output_freeswitch.wav"
    with open(output, "wb") as f:
        f.write(r.content)
    print(f"成功: {output} ({len(r.content)} bytes)")
else:
    print(f"失败: {r.json()}")
