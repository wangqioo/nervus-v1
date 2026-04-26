---
name: Spark2 服务器信息
description: Spark2 设备的 SSH 连接方式和主要服务部署概览
type: reference
originSessionId: 56390d81-9268-4c24-b6e3-3f3742ee2eb1
---
## SSH 连接

```
ssh -p 6002 wq@150.158.146.192
密码: 152535
主机名: spark-0138
```

## 主要服务（docker 容器）

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| Hermes | hermes | host 模式，API 在 8642 | AI Agent 后端，MiniMax M2.7 模型 |
| AnythingLLM | anythingllm | 3001 | 前端，连接 hermes 的 API |
| capyai-kb | 多容器 | — | 知识库 |
| ragflow | ragflow-app | — | RAG 服务 |
| linkbox | linkbox | — | 链接管理 |
| portainer | portainer | — | Docker 管理面板 |

## 目录结构

- `/home/wq/hermes-agent/` — hermes 源码，docker-compose 在此
- `/home/wq/.hermes/` — hermes 运行数据（root 权限，需 docker exec 访问）
- `/home/wq/apps/anythingllm/` — anythingllm docker-compose 及 storage

## Hermes 配置

- 模型：MiniMax-M2.7（provider: custom，base_url: https://api.minimax.chat/v1）
- API key 验证头：`Authorization: Bearer hermes-secret-key`
- 镜像：`hermes-agent:local`（本地构建，代码在镜像内 `/opt/hermes/`，非挂载）
- **修改代码后需要**：`docker cp` 进容器 + `docker restart hermes`

## AnythingLLM 配置

- LLM provider: generic-openai，指向 `http://172.17.0.1:8642/v1`（docker bridge IP）
- 模型名：hermes-agent
- API key：hermes-secret-key
