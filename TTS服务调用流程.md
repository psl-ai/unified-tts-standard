# TTS 四服务调用流程详解

## 前置：统一入口

```
tts_unified.py
    │
    ├── service="edge"   → http://127.0.0.1:8001/tts/{engine}
    ├── service="teleai" → http://127.0.0.1:8000/tts/{engine}
    ├── service="sherpa" → http://127.0.0.1:8002/tts/{engine}
    └── service="tianyi" → http://127.0.0.1:8900/tts/{engine}
```

---

## 一、Edge TTS 服务（端口 8001）

**引擎**：edge

**代码位置**：`edge-tts/app.py`

### 完整流程

```
步骤1: FastAPI 接收请求
  POST http://127.0.0.1:8001/tts/edge
  Header:  X-API-Key: my-fixed-key-2026
  Body:    {"text": "你好世界", "speed": 1.0, "pitch": 1.0, "volume": 1.0}
         │
         ▼
步骤2: 路由匹配 → 入口函数
  edge-tts/app.py:139  @app.post("/tts/edge")
  edge-tts/app.py:148  _engine_tts()
    ├── payload.engine = "edge"   // 路径覆盖 body 中的 engine
    └── 调用 _synthesize(payload)
         │
         ▼
步骤3: 认证检查
  edge-tts/app.py:150  Depends(verify_api_key)
  tts_common/auth.py:25 valid_tokens = {启动Token, 固定Key}
  tts_common/auth.py:29 x_api_key 不在集合中 → 401
                      x_api_key 在集合中 → 通过
         │
         ▼
步骤4: 参数转换
  edge-tts/app.py:91  _synthesize()
    ├── speed:  1.0 → speed_to_rate(1.0) → "+0%"       // utils.py:44
    ├── pitch:  1.0 → pitch_to_ssml(1.0) → "+0Hz"      // utils.py:22
    └── volume: 1.0 → volume_to_ssml(1.0) → "+0%"      // utils.py:33
         │
         ▼
步骤5: 构建合成输入
  edge-tts/app.py:59  generate_audio()
    ├── 无风格(style=general) → 纯文本
    └── 有风格(cheerful/sad/angry) → 构建 SSML XML
         │
         ▼
步骤6: 调用微软 Edge TTS
  edge-tts/app.py:72  edge_tts.Communicate(text, voice, rate, pitch, volume)
  edge-tts/app.py:74  async for chunk in communicate.stream():
                          只收集 type=="audio" 的帧
         │
         ▼
步骤7: 返回
  edge-tts/app.py:113  StreamingResponse(audio_bytes, media_type="audio/mpeg")
  Header: Content-Type: audio/mpeg
          X-Request-ID: <generated_uuid>
          X-TTS-Engine: edge
  Body:   二进制 MP3 数据
         │
         ▼
步骤8: 上游依赖
  微软 Edge TTS 在线服务（免费，无需 API Key）
```

---

## 二、TeleAI 服务（端口 8000）

**引擎**：edge, supernatural, realtime, offline

**代码位置**：`tts/app.py`

### 引擎分流

```
POST /tts/{engine}
    │
    ├── engine="edge"        → 走本地 edge-tts（流程同上）
    └── 其他(supernatural/    → 走上游 TeleAI API
           realtime/offline)
```

### TeleAI 合成流程

```
步骤1: FastAPI 接收请求
  POST http://127.0.0.1:8000/tts/supernatural
  Header:  X-API-Key: my-fixed-key-2026
  Body:    {"text": "你好", "voice": "xianliaonv", "format": "WAV"}
         │
         ▼
步骤2-3: 路由匹配 + 认证（同 Edge TTS 流程）
         │
         ▼
步骤4: 引擎分流
  tts/app.py:399  _synthesize()
    ├── payload.engine == "edge" → request_edge_tts()
    └── payload.engine != "edge" → request_tts()
         │
         ▼
步骤5: 构建上游请求
  tts/app.py:197  request_tts()
    ├── 生成 req_id
    └── build_upstream_payload()
        ├── timestamp: int(time.time())
        ├── req_id:    uuid
        ├── text:      payload.text
        ├── format:    "MP3"
        └── voice:     payload.voice
         │
         ▼
步骤6: 生成签名
  tts/app.py:117  generate_authorization(tts_url)
    ├── 拼接 signing_key_str = "teleai-cloud-auth-v1/{APP_ID}/QG/{timestamp}/43200"
    ├── HMAC-SHA256(APP_KEY, signing_key_str) → signing_key
    ├── 拼接 canonical_request = "POST\n/aipaas/voice/v1/tts/supernatural\n\nx-app-id:..."
    └── HMAC-SHA256(signing_key, canonical_request) → Authorization
         │
         ▼
步骤7: 发送 HTTP 请求到上游
  tts/app.py:213  requests.post(
      "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/supernatural",
      json=request_data,
      headers={X-APP-ID: "...", Authorization: "..."},
      timeout=120
  )
         │
         ▼
步骤8: 处理上游响应
  tts/app.py:228  response.status_code != 200 → 50202 错误
  tts/app.py:240  response.json()["result"]["audio"]
  tts/app.py:242  base64.b64decode(audio_base64)
  tts/app.py:253  audio_bytes 为空 → 50204 错误
         │
         ▼
步骤9: 返回
  tts/app.py:399  StreamingResponse(audio_bytes, media_type="audio/mpeg")
  Header: Content-Type: audio/mpeg
          X-Request-ID: <req_id>
          X-TTS-Engine: supernatural
  Body:   二进制 MP3 数据
         │
         ▼
步骤10: 上游依赖
  TeleAI 远程 API（需要 APP_ID + APP_KEY + 订阅对应服务）
```

---

## 三、Sherpa 服务（端口 8002）

**引擎**：sherpa, offline

**代码位置**：`tts4sherpav1.0/app.py`

### 完整流程

```
步骤1: FastAPI 接收请求
  POST http://127.0.0.1:8001/tts/sherpa
  Header:  X-API-Key: my-fixed-key-2026
  Body:    {"text": "你好", "voice": "0", "speed": 1.0, "format": "WAV"}
         │
         ▼
步骤2-3: 路由匹配 + 认证（同上）
         │
         ▼
步骤4: 加载模型（启动时一次性）
  tts4sherpav1.0/app.py:51-77  模块级别加载
    ├── sherpa_onnx.OfflineTtsMatchaModelConfig(
    │       acoustic_model="./matcha-icefall-zh-baker/model-steps-3.onnx",
    │       vocoder="./vocos-22khz-univ.onnx",
    │       data_dir="./matcha-icefall-zh-baker/data/lang_char",
    │   )
    └── sherpa_onnx.OfflineTts(tts_config)
         │
         ▼
步骤5: 参数解析
  tts4sherpav1.0/app.py:88  resolve_speed()
    ├── 优先读 payload.speed（顶层字段）
    └── fallback: payload.extra_params.get("speed", 1.0)
  
  tts4sherpav1.0/app.py:95  resolve_sid()
    ├── 优先读 extra_params.get("sid")
    └── fallback: payload.voice
         │
         ▼
步骤6: 本地 ONNX 推理
  tts4sherpav1.0/app.py:119  tts.generate(text, sid, speed)
    本地 CPU/GPU 推理，不依赖网络
         │
         ▼
步骤7: 返回
  tts4sherpav1.0/app.py:161  StreamingResponse(audio_bytes, media_type="audio/wav")
  Header: Content-Type: audio/wav
          X-TTS-Engine: sherpa
  Body:   二进制 WAV 数据
         │
         ▼
步骤8: 依赖
  本地 ONNX 模型文件（需提前下载放在 tts4sherpav1.0/ 目录）
  无需网络
```

---

## 四、Tianyi 服务（端口 8900）

**引擎**：supernatural, realtime, offline

**代码位置**：`tianyi_tts/app.py`

### 完整流程

```
步骤1: FastAPI 接收请求
  POST http://127.0.0.1:8900/tts/supernatural
  Header:  X-API-Key: my-fixed-key-2026
  Body:    {"text": "你好", "voice": "xianliaonv"}
         │
         ▼
步骤2-3: 路由匹配 + 认证（同上）
         │
         ▼
步骤4: 构建上游请求
  tianyi_tts/app.py:117  _synthesize()
    ├── 查找引擎对应的上游 URL
    ├── 生成 req_id
    └── 构建 request_data: {timestamp, req_id, text, voice, format}
         │
         ▼
步骤5: 生成签名
  tianyi_tts/app.py:79  _generate_authorization(url)
    ├── 规范化 URI 路径
    ├── canonical_headers = "x-app-id:{APP_ID}"
    ├── HMAC-SHA256 生成签名 → Authorization header
         │
         ▼
步骤6: 发送 HTTP 请求到上游
  tianyi_tts/app.py:128  requests.post(
      "https://openapi.teleagi.cn:443/aipaas/voice/v1/tts/supernatural",
      json=request_data,
      headers={X-APP-ID: "97316fce...", Authorization: "..."},
      timeout=120
  )
         │
         ▼
步骤7: 处理上游响应
  tianyi_tts/app.py:146  resp.json()
    ├── status != 10000 → 50202 错误
    └── result.audio → base64.b64decode()
         │
         ▼
步骤8: 返回
  tianyi_tts/app.py:174  StreamingResponse(audio_bytes, media_type_for(audio_fmt))
  Header: Content-Type: audio/mpeg (或 audio/wav)
          X-TTS-Engine: supernatural
  Body:   二进制音频数据
         │
         ▼
步骤9: 依赖
  TeleAI 远程 API（需要 APP_ID + APP_KEY + 订阅超自然语音服务）
  当前状态：上游返回 403，需订阅后可用
```

---

## 五、对比总结

| 步骤 | Edge TTS | TeleAI | Sherpa | Tianyi |
|------|----------|--------|--------|--------|
| 1. 接收请求 | FastAPI | FastAPI | FastAPI | FastAPI |
| 2. 路由 | `/tts/edge` | `/tts/{4个引擎}` | `/tts/{2个引擎}` | `/tts/{3个引擎}` |
| 3. 认证 | X-API-Key | X-API-Key | X-API-Key | X-API-Key |
| 4. 参数处理 | float→SSML | 不变 | resolve_speed/sid | 不变 |
| 5. 合成方式 | edge-tts 库 | HTTP 调用 | ONNX 推理 | HTTP 调用 |
| 6. 上游地址 | 微软云 | teleagi.cn | 本地 CPU/GPU | teleagi.cn |
| 7. 输出格式 | MP3 | MP3 | WAV | MP3/WAV/FLAC |
| 8. 返回方式 | StreamingResponse | StreamingResponse | StreamingResponse | StreamingResponse |
```

| 服务 | 端口 | 引擎 | 需要网络 | 状态 |
|------|------|------|---------|------|
| Edge TTS | 8001 | edge | 是（微软） | 可用 |
| TeleAI | 8000 | supernatural/realtime/offline/edge | 是 | 需确认 |
| Sherpa | 8002 | sherpa/offline | 否 | 需模型 |
| Tianyi | 8900 | supernatural/realtime/offline | 是 | 需订阅 |
