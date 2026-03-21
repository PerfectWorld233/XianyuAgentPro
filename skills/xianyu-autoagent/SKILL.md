---
name: xianyu-autoagent
description: Xianyu AutoAgent 项目开发助手 - 帮助快速配置、启动和优化 AI 客服机器人
---

# Xianyu AutoAgent 开发助手

## 概述

这是一个 Claude Code skill，用于加速 XianyuAutoAgent 项目的开发工作流。该项目是一个 AI 驱动的闲鱼自动化客服机器人系统。

该 skill 帮助开发者快速完成：
- 环境配置验证和初始化
- 项目启动和运行
- Prompt 调试和优化
- WebSocket 连接和 Token 管理问题排查
- 日志分析和性能监控

## 工作流

 

### 开发任务
- 修改 / 新增提示词 -> `prompts/` 目录下的 `*_prompt.txt` 文件
- 调整议价策略 -> 编辑 `price_prompt.txt`
- 改进意图分类 -> 编辑 `classify_prompt.txt`
- 增强技术支持 -> 编辑 `tech_prompt.txt`
- 修改默认回复 -> 编辑 `default_prompt.txt`

### 问题排查
- 消息未收到 / 未回复 -> 查看 `main.py` 的消息过滤逻辑
- Token 过期 -> 更新 `COOKIES_STR` 环境变量
- WebSocket 连接中断 -> 检查心跳和重连机制
- LLM 回复异常 -> 检查 prompt 文件和安全过滤规则

### 创建 PR
常见的改进方向：
- 新增或优化 prompt
- 改进消息处理和过滤逻辑
- 增强议价策略
- 支持新的平台功能
- 优化性能和稳定性

未来规划的功能（供参考）：
- CRM 集成 / 数据分析
- 情感分析增强
- RAG 知识库
- 钉钉集成
- Web 管理界面

## 关键文件

详见 `references/project-map.md`

## 常见问题

1. **环境配置问题** - 检查 `.env` 文件的必要配置项
2. **消息过滤异常** - 查看 `main.py` 的消息验证函数
3. **LLM 生成失败** - 检查 prompt 文件编码和格式
4. **连接不稳定** - 调整 `HEARTBEAT_INTERVAL` 和 `TOKEN_REFRESH_INTERVAL`
5. **Cookie 失效** - 重新从浏览器获取并更新 `COOKIES_STR`

## 参考资源

- 查看完整架构 -> `references/project-map.md`
- 查看开发工作流 -> `references/development-workflow.md`
- Electron 桌面端开发 -> `../electron-dev/SKILL.md`
