# 开发工作流指南

## 快速启动流程

### 1. 项目初始化

```bash
# 克隆项目
git clone https://github.com/shaxiu/XianyuAutoAgent.git
cd XianyuAutoAgent

# 安装依赖
pip install -r requirements.txt

# 创建环境配置
cp .env.example .env
# 编辑 .env，填写：
# - API_KEY（从 Qwen 平台获取）
# - COOKIES_STR（从浏览器 DevTools 获取）
```

### 2. 启动机器人

```bash
python main.py
```

## 常见开发任务

### 任务 1：调整 AI 回复行为

**修改步骤**：
1. 编辑 `prompts/default_prompt.txt`（或其他 prompt 文件）
2. 修改提示词内容
3. 重启机器人，测试回复效果

**Prompt 文件对应的 Agent**：
- `classify_prompt.txt` -> 意图分类（决定该用哪个专家）
- `price_prompt.txt` -> 议价专家（处理价格谈判）
- `tech_prompt.txt` -> 技术专家（处理技术问题）
- `default_prompt.txt` -> 通用客服（处理其他问题）

**调试技巧**：
- 查看 `main.py` 日志，找到"路由到 Agent: xxx"来确认使用了哪个专家
- 在 prompt 中添加示例可以改进 LLM 的行为
- 使用短句和清晰的指示会更有效

### 任务 2：改进意图分类

**修改步骤**：
1. 编辑 `prompts/classify_prompt.txt`
2. 增加新的意图分类或改进现有分类逻辑
3. 确保输出格式保持一致（便于路由）
4. 测试新增的意图类型

**关键点**：
- 分类结果用于决定使用哪个 Agent
- 分类要清晰，避免歧义
- 可以支持多标签分类

### 任务 3：调整议价策略

**修改步骤**：
1. 编辑 `prompts/price_prompt.txt`
2. 调整降价幅度、次数限制、谈判策略
3. 测试不同价格输入的回复

**关键配置**：
- `context_manager.py` 中的议价次数统计可以限制最多降价次数
- Prompt 中可以根据商品价格制定差异化策略

### 任务 4：处理消息过滤问题

**问题诊断**：
- 查看 `main.py` 中的以下函数：
  - `is_chat_message()` - 判断是否真实客户消息
  - `is_system_message()` - 过滤系统消息
  - `is_typing_status()` - 忽略"正在输入"状态
  - `is_sync_package()` - 处理消息同步

**修改步骤**：
1. 检查消息是否通过了所有过滤
2. 如需修改过滤逻辑，在上述函数中调整
3. 添加日志验证修改效果

**常见问题**：
- 消息未到达 Bot -> 检查 `is_chat_message()` 逻辑
- 系统消息被当作客户消息 -> 检查 `is_system_message()` 逻辑
- 消息处理延迟 -> 检查消息过期时间配置

### 任务 5：处理安全过滤问题

**当前过滤规则**（见 `XianyuAgent.py`）：
```
blocked_phrases = ["微信", "QQ", "支付宝", "银行卡", "线下"]
```

**修改步骤**：
1. 编辑 `_safe_filter()` 方法
2. 添加或移除敏感词
3. 测试边界情况

**注意**：
- 过滤太严格会导致有用信息被过滤
- 过滤太松会暴露用户隐私
- 建议定期审查过滤效果

## WebSocket 和 Token 管理

### Token 过期处理

**症状**：
- 机器人停止接收消息
- 日志显示 "Token 刷新失败"
- WebSocket 连接断开

**解决步骤**：
1. 打开浏览器 DevTools（F12）
2. 进入 Network 标签
3. 查找并复制新的 Cookie
4. 更新 `.env` 中的 `COOKIES_STR`
5. 重启机器人

**配置调整**：
- `TOKEN_REFRESH_INTERVAL` - Token 刷新间隔（默认 3600 秒）
- `TOKEN_RETRY_INTERVAL` - Token 刷新失败重试间隔（默认 300 秒）

### WebSocket 连接问题

**症状**：
- 连接频繁断开
- 心跳超时
- 消息丢失

**调试步骤**：
1. 检查心跳配置：
   - `HEARTBEAT_INTERVAL` - 心跳发送间隔（默认 15 秒）
   - `HEARTBEAT_TIMEOUT` - 心跳超时时间（默认 5 秒）

2. 增加日志级别，观察心跳和重连日志

3. 可能的调整：
   - 增加 `HEARTBEAT_INTERVAL` 值（降低频率）
   - 增加 `HEARTBEAT_TIMEOUT` 值（给更多响应时间）

## 创建 PR 的工作流

### 1. 确认修改范围

常见的改进 PR：
- ✅ 修改或新增 Prompt
- ✅ 改进消息处理逻辑
- ✅ 增强议价策略
- ✅ 优化性能和稳定性
- ✅ 修复 Bug
- ✅ 更新文档

不适合的 PR（这些是长期规划）：
- ❌ 完整的 CRM 集成
- ❌ Web 管理界面
- ❌ 情感分析模块
- ❌ RAG 知识库（没有基础设施）

### 2. 分支和提交

```bash
# 创建特性分支
git checkout -b feature/your-feature-name

# 提交更改
git add .
git commit -m "描述改进内容"

# 推送到远程
git push origin feature/your-feature-name
```

### 3. 提交 PR 时的检查清单

- [ ] 修改内容清晰、专注
- [ ] 代码遵循现有风格
- [ ] Prompt 修改已测试过效果
- [ ] 添加了有意义的 Git 提交信息
- [ ] 没有提交敏感信息（API Key、Cookie 等）
- [ ] 更新了相关文档

## 调试技巧

### 启用详细日志

默认已配置 loguru 日志，可以查看：
- 消息接收状态
- Agent 路由结果
- LLM 请求和响应
- 数据库操作

### 在代码中添加调试

```python
from loguru import logger

logger.debug(f"调试信息: {variable}")
logger.info(f"重要信息: {variable}")
logger.warning(f"警告: {variable}")
logger.error(f"错误: {variable}")
```

### 查看数据库内容

```python
# 可以使用 sqlite3 CLI 查看数据库
sqlite3 data/chat_history.db
# 然后执行 SQL 查询，如：
# SELECT * FROM messages LIMIT 10;
```

## 性能优化建议

1. **消息处理** - 优化过滤逻辑，减少不必要的字符串操作
2. **数据库** - 定期清理过期消息，维护索引
3. **LLM 调用** - 复用 OpenAI 客户端实例，使用连接池
4. **内存管理** - 监控对话历史大小，设置合理的 `max_history` 值

## 常见问题排查表

| 问题 | 可能原因 | 解决方案 |
|------|--------|--------|
| 消息未被回复 | 消息被过滤了 | 检查 `is_chat_message()` |
| AI 回复不合适 | Prompt 不够清晰 | 优化 Prompt 或选择更好的示例 |
| Token 频繁过期 | Cookie 不稳定 | 从浏览器重新获取 Cookie |
| WebSocket 连接断开 | 心跳配置或网络问题 | 调整 HEARTBEAT_* 参数 |
| LLM API 错误 | API Key 或模型配置 | 检查 .env 中的 API_KEY 和 MODEL_NAME |
| 数据库锁定 | 并发写入冲突 | 检查是否同时运行多个实例 |
