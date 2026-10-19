# TTS 统一 HTTP API 标准

本目录下所有 TTS 服务均遵循相同的 HTTP 接口契约。

## 架构

共享代码位于 `tts_common/`，包含数据模型、错误处理、认证和工具函数。

### 服务列表

| 服务 | 目录 | 端口 | 引擎 | 类型 |
|------|------|------|------|------|
| TeleAI | `tts/` | 8000 | edge, supernatural, realtime, offline | 远程 API |
| Edge TTS | `edge-tts/` | 8001 | edge | 微软免费 |
| Sherpa | `tts4sherpav1.0/` | 8002 | sherpa, offline | 本地 ONNX |
| Tianyi | `tianyi_tts/` | 8900 | supernatural, realtime, offline | 远程 API |
| Gateway | `tts_gateway/` | 9000 | 全部转发 | 统一入口 |

## 端点

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/health` | 需要 | 健康检查 |
| `HEAD` | `/tts` | 需要 | 音频响应预检 |
| `POST` | `/tts` | 需要 | 统一合成（引擎在请求体中指定） |
| `POST` | `/tts/{engine}` | 需要 | 引擎直连合成（直接传 URL 调用指定引擎） |

每个服务支持的引擎直连路由：

| 服务 | 引擎直连 URL |
|------|-------------|
| TeleAI | `/tts/edge`、`/tts/supernatural`、`/tts/realtime`、`/tts/offline` |
| Edge TTS | `/tts/edge` |
| Sherpa | `/tts/sherpa`、`/tts/offline` |
| Tianyi | `/tts/supernatural`、`/tts/realtime`、`/tts/offline` |
| Gateway | 全部引擎，统一入口 `http://host:9000` |

`POST /text/` 仅作为隐藏兼容端点保留。

## 认证

所有端点均需认证。认证方式有两种：

1. **启动时生成的会话 Token**（每次启动服务时生成）
2. **固定 API Key**（通过环境变量 `TTS_API_KEY` 配置）

调用 API 时需在请求头中携带：

```http
X-API-Key: <TTS_API_KEY>
```

认证失败返回：

```json
{
  "code": 40100,
  "message": "Missing or invalid API key.",
  "details": null
}
```

## 合成请求

两种调用方式均可：

**方式一：引擎在请求体中指定**
```http
POST /tts
Content-Type: application/json
X-API-Key: <token>
```
```json
{
  "text": "你好",
  "engine": "edge",
  ...
}
```

**方式二：直接调用引擎 URL（引擎已在路径中）**
```http
POST /tts/edge
Content-Type: application/json
X-API-Key: <token>
```
```json
{
  "text": "你好",
  ...
}
```
引擎字段在方式二中可省略，自动使用路径中的引擎。

```json
{
  "text": "你好，欢迎使用统一 TTS 服务。",
  "engine": "edge",
  "voice": "zh-CN-XiaoxiaoNeural",
  "format": "WAV",
  "req_id": "optional-request-id",
  "extra_params": {},
  "speed": 1.0,
  "pitch": 1.0,
  "style": "general",
  "volume": 1.0,
  "sample_rate": 16000
}
```

### 通用字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `text` | string | 是 | — | 待合成的文本内容 |
| `engine` | string | 否 | 见引擎默认值 | TTS 引擎名称 |
| `voice` | string | 否 | 见引擎默认值 | 语音角色或说话人标识 |
| `format` | string | 否 | 见引擎默认值 | 音频输出格式（MP3/WAV/FLAC） |
| `req_id` | string | 否 | 自动生成 UUID | 请求追踪 ID |
| `extra_params` | object | 否 | `{}` | 引擎特有附加参数 |
| `speed` | float | 否 | `1.0` | 语速倍数（1.0=正常，1.2=增强 20%） |
| `pitch` | float | 否 | `1.0` | 音调倍数（1.0=正常，1.1=提高 10%） |
| `style` | string | 否 | `"general"` | 语音风格，如 cheerful/sad/angry |
| `volume` | float | 否 | `1.0` | 音量倍数（1.0=正常，1.2=增强 20%） |
| `sample_rate` | int | 否 | `16000` | 采样率，可选 8000/16000/22050/24000/32000/44100/48000 |

### 向后兼容

已有调用方可使用 `"input"` 替代 `"text"`，两种字段均可接受。
新接入必须使用 `"text"`。

### 引擎特性说明

- **edge**（Edge TTS / TeleAI）：支持 `speed`、`pitch`、`style`、`volume`。输出格式：MP3。
- **sherpa / offline**（Sherpa）：通过顶层字段或 `extra_params.speed`（向后兼容）支持 `speed`。说话人 ID 通过 `voice`（数字字符串）或 `extra_params.sid` 设置。`pitch`/`style`/`volume` 字段可传入但不作用于音频。输出格式：WAV。
- **supernatural / realtime / offline**（TeleAI / Tianyi）：调用 TeleAI 远程 API。输出格式：MP3/WAV/FLAC。

## 成功响应

成功响应的 body 为二进制音频数据。响应头包含：

```http
Content-Type: audio/mpeg | audio/wav | audio/flac
Content-Disposition: inline; filename="<req_id>.<extension>"
Content-Length: <bytes>
X-Request-ID: <req_id>
X-TTS-Engine: <engine>
```

## 错误响应

所有错误响应使用统一的 JSON 结构：

```json
{
  "code": 42200,
  "message": "Invalid request body.",
  "details": []
}
```

| HTTP 状态码 | 业务码 | 说明 |
|---|---|---|
| `401` | `40100` | API 密钥缺失或无效 |
| `422` | `42200` | 请求体参数不合法 |
| `500` | `50001` | 本地合成失败（如 Sherpa ONNX） |
| `502` | `50201` | 上游 TTS 请求失败 |
| `502` | `50202` | 上游返回非 200 状态码 |
| `502` | `50203` | 上游响应缺少音频数据 |
| `502` | `50204` | 上游返回空音频 |
| `502` | `50210` | Edge TTS 合成失败 |
| `502` | `50211` | Edge TTS 返回空音频 |

