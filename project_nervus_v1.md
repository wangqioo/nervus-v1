---
name: Nervus v1 项目进度
description: Nervus 项目里程碑记录和当前开发状态
type: project
originSessionId: 2b0dc1e9-086b-4bc4-b32a-f702c0f45247
---
## 当前版本：v1.2

**Why:** 去掉模拟手机壳、灵动岛、假状态栏，改为全屏 Web App，准备 Capacitor iOS 套壳

**How to apply:** 下一步是用 webshell-app 的 Capacitor 配置将 Nervus 打包为 iOS 应用，server.url 指向 Orin IP:8900

---

## 已完成里程碑

### v1.2 — iOS 全屏化（2026-04-26）
- 移除模拟手机壳、灵动岛（.di）、假状态栏（.sb）、侧边按钮伪元素
- body/.phone 改为 `position:fixed;inset:0`（全屏）
- CSS --PW/--PH 从 390px/844px 改为 100vw/100dvh
- .panels/.panel 位置全部用 CSS 变量 calc() 表达
- JS nav() 每次读取 window.innerWidth/Height，支持旋转
- 各面板内容区加 max(原有px, env(safe-area-inset-top)+xpx) 适配 iOS 刘海
- viewport 添加 viewport-fit=cover
- specGoToPage 和 spec scroll dot 的 390 换成动态 PW

### v1.1 — 文件传输助手接入（2026-04-26）
- transmission_assistant 整体复制进 `apps/file-manager/`（端口 8015）
- iframe 嵌入 Nervus Files 面板（左划）
- 修复：Caddy 路由 `/api/files*`、iframe 布局、右滑返回 postMessage、图片立即预览、缓存头

---

## 待开发项

### 已有后端、前端待联通（11 个）
- 提醒、日历、个人笔记、会议纪要、热量管理
- 视频转录、PDF提取、RSS订阅、相册处理、知识库、工作流

### 需新建后端（5 个）
- 闹钟（纯前端）、密码本、MBTI陪伴、勋章系统、电子宠物、健康趋势

### 主面板待联通
- 感知面板（sense + status-sense 后端已有）
- Chat 面板（接本地 LLM）

---

## 基础设施
- 部署在 Orin Nano：`ssh -p 6000 nvidia@150.158.146.192`（密码 nvidia）
- **Orin 实际路径**：`/home/nvidia/nervus/`（不是 nervus-core-linkbox，scp 用这个路径）
- 本地开发路径：`/Users/wq/nervus-core-linkbox/`
- GitHub：https://github.com/wangqioo/nervus-v1.git
- 代码同步：GitHub 无法直连，用 scp 传文件到 Orin
