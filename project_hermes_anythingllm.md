---
name: Hermes + AnythingLLM 部署
description: hermes 作为 AI agent 后端、AnythingLLM 作为前端的架构、已知问题及解决方案
type: project
originSessionId: 56390d81-9268-4c24-b6e3-3f3742ee2eb1
---
## 架构

```
AnythingLLM (3001) → hermes API (8642) → MiniMax API (minimax.chat/v1)
```

AnythingLLM 通过 `http://172.17.0.1:8642/v1`（docker bridge）访问 hermes 的 OpenAI 兼容接口。

## 已解决问题：AnythingLLM 中响应卡住

**现象**：在 AnythingLLM 中对话，回复说到一半卡住，报"传输响应时发生错误"。

**根本原因**：MiniMax M2.7 是推理模型，回复时在 `delta.content` 里直接输出 `<think>思考过程</think>` XML 标签。AnythingLLM 不识别这种格式（它只处理 `delta.reasoning_content` 字段，即 DeepSeek 格式），导致渲染卡死。

**解决方案**：在 hermes 的 `api_server.py` 的 `_on_delta` 回调里过滤掉 `<think>...</think>` 块，再送入 SSE 流。

**改动位置**：
- 文件：`/home/wq/hermes-agent/src/gateway/platforms/api_server.py`
- 容器内路径：`/opt/hermes/gateway/platforms/api_server.py`
- 注意：hermes 镜像是本地构建的，代码在镜像内，**不是**通过 volume 挂载。修改后必须 `docker cp` 进容器再 `docker restart`。

**关键注意事项**：
- `<think>` 和 `</think>` 可能被拆在不同 chunk 里，必须做跨 chunk 的状态追踪
- 用单元素 list（`[False]`、`[""]`）在闭包内保持状态
- `</think>` 后模型会输出 `\n\n`，需在第一个有效 chunk 前 lstrip 掉
- 备份文件在：`/home/wq/hermes-agent/src/gateway/platforms/api_server.py.bak`

**部署命令**：
```bash
docker cp /home/wq/hermes-agent/src/gateway/platforms/api_server.py hermes:/opt/hermes/gateway/platforms/api_server.py
docker restart hermes
```

## 其他注意事项

- MiniMax 会偶发 HTTP 529（服务过载），属于上游问题，稍后重试即可
- MiniMax-Text-01 模型当前账号套餐不支持，使用 MiniMax-M2.7
- hermes API server 默认 host 是 `127.0.0.1`，但实际部署时已监听 `0.0.0.0:8642`
