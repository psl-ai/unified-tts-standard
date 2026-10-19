"""TTS 演示测试脚本 — 把 Token 贴进去直接运行"""
import requests

TOKEN = "把启动时打印的Token贴在这里"
URL   = "http://127.0.0.1:8001"

def test(name, **kwargs):
    r = requests.post(f"{URL}/tts/edge", json=kwargs, headers={"X-API-Key": TOKEN}, timeout=30)
    print(f"[{r.status_code}] {name}")
    if r.status_code != 200:
        print(f"  {r.json()}")
    else:
        print(f"  音频 {len(r.content)} bytes")
    return r

# ===== 正式演示 =====
print("=" * 50)
print("1. 基础合成")
print("=" * 50)
r = test("基础合成", text="你好，欢迎使用统一TTS服务")
if r.status_code == 200:
    open("D:/tts统一标准/tts/demo.mp3", "wb").write(r.content)
    print("  已保存 demo.mp3")

print()
print("=" * 50)
print("2. 调整语速 (speed=1.5)")
print("=" * 50)
test("加速", text="这段话的语速会快一些", speed=1.5)

print()
print("=" * 50)
print("3. 调整音调 (pitch=1.2)")
print("=" * 50)
test("高音调", text="这段话音调会高一些", pitch=1.2)

print()
print("=" * 50)
print("4. 调整音量 (volume=1.5)")
print("=" * 50)
test("大音量", text="这段话音量会大一些", volume=1.5)

print()
print("=" * 50)
print("5. 欢快风格 (style=cheerful)")
print("=" * 50)
test("欢快", text="今天真是太开心了", style="cheerful")

print()
print("=" * 50)
print("6. 指定采样率 (sample_rate=16000)")
print("=" * 50)
test("低采样率", text="低采样率测试", sample_rate=16000)

print()
print("=" * 50)
print("7. 参数校验 — 非法采样率")
print("=" * 50)
test("参数校验", text="测试", sample_rate=99999)
