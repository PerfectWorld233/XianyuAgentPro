---
name: electron-dev
description: Electron 桌面应用开发测试助手 - 帮助快速启动开发环境、排查 IPC / 进程通信问题、调试前端 UI 和打包发布
---

# Electron 桌面应用开发测试助手

## 概述

该 skill 专注于 XianyuAutoAgent 的 Electron 桌面端开发工作流，覆盖：

- 本地开发环境启动与热更新
- Electron 主进程 / Python 子进程通信调试
- Vue 3 前端 UI 开发与调试
- IPC 通道新增与排查
- 打包构建与安装包制作

## 项目结构速查

详见 `references/electron-map.md`

## 工作流

### 启动开发环境

```bash
cd electron
npm install          # 首次或依赖变更后执行（含 electron-rebuild）
npm run dev          # 同时启动 Vite dev server + Electron
```

> 开发模式下 `VITE_DEV_SERVER_URL` 环境变量被设置，Electron 自动加载 `http://localhost:5173`，并打开 DevTools。
> Python 后端使用 `python bridge.py` 直接运行，无需 PyInstaller。

### 常见开发任务

- 修改前端 UI → `electron/renderer/src/views/` 或 `components/`
- 新增 IPC 通道 → `ipcHandlers.js` + `preload.js` + Vue 页面三处同步修改
- 调整 Python 通信协议 → `pythonManager.js` + `bridge.py` 同步修改
- 修改配置读写逻辑 → `dbManager.js`（主进程）+ `config_manager.py`（Python）

### 问题排查

- Python 进程未启动 / 无日志输出 → 检查 `pythonManager.js` spawn 路径和 `PYTHONUNBUFFERED=1`
- IPC 调用无响应 → 确认 `preload.js` 已暴露、`ipcHandlers.js` 已注册对应通道
- 前端白屏 → 检查 Vite 是否正常启动，或 `renderer/dist/` 是否存在（生产模式）
- `better-sqlite3` 加载失败 → 执行 `electron-rebuild -f -w better-sqlite3`
- Cookie / 配置未持久化 → 检查 `%APPDATA%\XianyuAutoAgent\app_config.db`

### 打包构建

```bat
# 一键全量打包（推荐）
scripts\build-all.bat

# 分步执行
scripts\build-python.bat          # Step 1: PyInstaller
cd electron && npm run build:renderer  # Step 2: Vite
npm run build:electron             # Step 3: electron-builder
```

## 关键文件

详见 `references/electron-map.md`

## 常见问题

1. **npm run dev 启动失败** - 检查 Node.js 版本（要求 18+）和 `electron-rebuild` 是否执行
2. **Python 日志不出现在 UI** - 确认 `listeners` 字典中有对应 `type` 的 key
3. **新增 IPC 通道不生效** - 三处必须同时修改：`ipcHandlers.js` / `preload.js` / Vue 组件
4. **打包后找不到 Python 可执行文件** - 检查 `electron-builder.yml` 中 `extraResources` 路径配置
5. **扫码登录弹不出浏览器** - 确认已执行 `playwright install chromium`
