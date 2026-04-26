---
name: llama.cpp 上下文限制问题
description: 文件管理AI搜索超限，llama.cpp 上下文窗口仅1024 tokens
type: project
originSessionId: 4d943b1c-22a0-4a0c-a1df-a8ec145b958e
---

## 问题

文件管理 AI 搜索（`/api/files/search`）调用 `search_files()` 时，请求 token 数超出 llama.cpp 上下文窗口限制（1024 tokens），导致 502 错误：

```
llama.cpp 400: request (1469 tokens) exceeds the available context size (1024 tokens)
```

根因：搜索 prompt 包含完整文件列表（文件名、类型、摘要、关键词），文件稍多就超限。

## 触发场景

- 文件列表较长时（>20个文件）
- 搜索请求 token 数 > 1024

## 优化方向

1. **扩大 llama.cpp 上下文窗口**（主攻方向）：边缘计算芯片优化后，将上下文窗口从 1024 提升到更大（如 4K/8K）
2. **Prompt 压缩**：搜索结果合并时减少冗余描述
3. **分批处理**：先初筛再精排

## 相关代码

- `apps/file-manager/backend/services/analyzer.py` — `search_files()` 函数
- `core/arbor/nervus_platform/models/service.py` — llama.cpp 调用
- `core/arbor/nervus_platform/models/schemas.py` — ChatResponse schema（含 reasoning_content）

## 现状

- 已回退临时批处理代码，等上下文扩大后直接用原逻辑
- 其他 AI 功能（图片分析、链接分类、文档摘要）正常