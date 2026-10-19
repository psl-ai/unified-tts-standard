import requests, json

r = requests.post(
    "http://127.0.0.1:8900/tts/supernatural",
    json={
        "text":        "你好世界",
        "voice":       "xianliaonv",
        "format":      "MP3",
        "speed":       1.0,
        "pitch":       1.0,
        "style":       "general",
        "volume":      1.0,
        "sample_rate": 16000,
        "req_id":      "test-001",
        "extra_params": {},
    },
    headers={"X-API-Key": "my-fixed-key-2026"},
)

print(r.status_code)
if r.status_code == 200:
    open("D:/tts统一标准/tts/test.mp3", "wb").write(r.content)
    print("OK, saved test.mp3")
else:
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))
