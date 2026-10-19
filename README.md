# 统一 TTS 语音合成服务网关

面向语音客服场景，整合 Edge TTS、TeleAI、天翼 TTS 和 Sherpa ONNX 等多种语音引擎，设计统一 HTTP API 和网关服务，屏蔽不同引擎的调用差异。

## 功能特性

- **统一 API 网关**：设计统一 TTS HTTP 网关 API，完成参数规范、HMAC 认证、错误码定义、音频响应及旧接口兼容
- **多引擎适配**：对接 Edge-TTS、天翼 TTS、Sherpa ONNX 等多引擎，实现路由分发、参数校验与音频流返回
- **Docker Compose 部署**：完成多服务部署，编写 4 组接口测试脚本，预置 19 项健康检查、参数校验和语音合成检查
- **离线推理支持**：集成 Sherpa ONNX 本地推理引擎，无需依赖云端 TTS 服务

## 技术栈

| 层级 | 技术选型 |
|---|---|
| 网关框架 | Python HTTP 服务 |
| TTS 引擎 | Edge TTS、TeleAI、天翼 TTS、Sherpa ONNX |
| 部署 | Docker、Docker Compose |
| 认证 | HMAC 签名认证 |

## 支持的 TTS 引擎

| 引擎 | 类型 | 特点 |
|---|---|---|
| Edge TTS | 云端 | 免费、音色丰富 |
| 天翼 TTS | 云端 | 电信级稳定、中文效果好 |
| TeleAI | 云端 | 大模型语音合成 |
| Sherpa ONNX | 本地 | 离线推理、低延迟 |

## 快速开始

### Docker 部署

```bash
docker compose up --build
```

### 本地开发

```bash
pip install -r requirements.txt
python tts_unified.py
```

## 项目结构

```
Unified TTS Standard/
├── tts_unified.py          # 统一网关入口
├── API_STANDARD.md         # API 接口标准文档
├── 使用手册.md             # 使用说明
├── docker-compose.yml      # 多服务编排
├── Dockerfile              # 镜像构建
├── edge-tts/               # Edge TTS 适配
├── tele tts/               # TeleAI TTS 适配
├── tianyi_tts/             # 天翼 TTS 适配
├── tts4sherpav1.0/         # Sherpa ONNX 本地引擎
├── tts_common/             # 公共工具
└── tts_gateway/            # 网关核心
```

## API 调用示例

```bash
POST /api/tts/synthesize
{
  "text": "你好，很高兴为您服务",
  "engine": "edge",
  "voice": "zh-CN-XiaoxiaoNeural",
  "format": "mp3"
}
```

返回音频流，支持 mp3、wav 等格式。
