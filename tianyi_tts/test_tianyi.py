"""Tianyi TTS 完整参数测试"""

import requests

URL = "http://127.0.0.1:8900"
KEY = "my-fixed-key-2026"
H = {"X-API-Key": KEY}

def test(name, **kwargs):
    r = requests.post(f"{URL}/tts/supernatural", json=kwargs, headers=H, timeout=120)
    print(f"[{r.status_code}] {name}")
    if r.status_code == 200:
        fn = f"D:/tts统一标准/tts/tianyi_{name.replace(' ','_')}.mp3"
        open(fn, "wb").write(r.content)
        print(f"  保存: {fn}  ({len(r.content)} bytes)")
    else:
        try:
            print(f"  {r.json()}")
        except:
            print(f"  {r.text[:300]}")
    print()

# ===== 正式测试 =====

# 默认参数
test("默认参数", text="你好世界")

# 指定语音角色
test("指定语音", text="欢迎使用天翼TTS服务", voice="xianliaonv")

# 调整语速
test("加速", text="这段话的语速会快一些", speed=1.5)

# 调整音调
test("高音调", text="这段话音调会高一些", pitch=1.2)

# 调整音量
test("大音量", text="这段话音量会大一些", volume=1.5)

# 指定采样率
test("指定采样率", text="低采样率测试", sample_rate=16000)

# 指定格式
test("WAV格式", text="输出WAV格式", format="WAV")

# 请求追踪ID
test("请求追踪", text="带追踪ID的请求", req_id="my-test-001")

# 完整参数
test("完整参数", text="你好世界，这是完整参数测试",
     voice="xianliaonv", format="MP3", speed=1.0,
     pitch=1.0, volume=1.0, sample_rate=24000,
     req_id="test-001", extra_params={})

print("测试完成，音频文件保存在 D:/tts统一标准/tts/ 目录下")
