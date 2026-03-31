"""
bridge.py — IPC bridge between Electron and the XianyuAutoAgent Python backend.

Communication protocol: JSON lines on stdout (to Electron) / stdin (from Electron).

Outbound message types:
  {"type": "log",                    "level": "info|debug|warning|error", "message": "...", "time": "ISO"}
  {"type": "status",                 "running": true|false}
  {"type": "error",                  "code": "...", "message": "..."}
  {"type": "generate_prompts_result","success": true|false, "prompts": {...}, "message": "..."}

Inbound commands:
  {"cmd": "start"}
  {"cmd": "stop"}
  {"cmd": "reload_config"}
  {"cmd": "generate_prompts", "chat_log": "..."}
"""

import asyncio
import json
import os
import sys
import threading

# Force UTF-8 stdout/stderr on Windows (prevents GBK encoding issues)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

from loguru import logger


# ---------------------------------------------------------------------------
# Resource path helper (PyInstaller compatibility)
# ---------------------------------------------------------------------------

def get_resource_path(rel: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(__file__), rel)


# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------

def get_data_dir() -> str:
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    data_dir = os.path.join(appdata, 'XianyuAutoAgent')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


# ---------------------------------------------------------------------------
# Stdout JSON sink for loguru
# ---------------------------------------------------------------------------

def stdout_json_sink(message):
    record = message.record
    payload = {
        "type": "log",
        "level": record["level"].name.lower(),
        "message": record["message"],
        "time": record["time"].isoformat(),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def emit_status(running: bool):
    payload = {"type": "status", "running": running}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def emit_error(code: str, message: str):
    payload = {"type": "error", "code": code, "message": message}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def emit_generate_prompts_result(success: bool, prompts: dict = None, message: str = ""):
    payload = {
        "type": "generate_prompts_result",
        "success": success,
        "prompts": prompts or {},
        "message": message,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Stdin reader thread (Windows asyncio stdin not reliable)
# ---------------------------------------------------------------------------

def stdin_thread(cmd_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                cmd = json.loads(line)
                loop.call_soon_threadsafe(cmd_queue.put_nowait, cmd)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Bridge main
# ---------------------------------------------------------------------------

class BridgeManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.config_db_path = os.path.join(data_dir, 'app_config.db')
        self.chat_db_path = os.path.join(data_dir, 'chat_history.db')
        self.config_manager = None
        self.bot_task: asyncio.Task = None
        self.generate_task: asyncio.Task = None
        self.knowledge_task: asyncio.Task | None = None
        self.knowledge_manager: 'KnowledgeManager | None' = None
        self.knowledge_retriever: 'KnowledgeRetriever | None' = None

    def load_modules(self):
        """Import project modules (supports both source and PyInstaller bundle)."""
        # Ensure the package directory is on sys.path
        pkg_dir = get_resource_path('.')
        if pkg_dir not in sys.path:
            sys.path.insert(0, pkg_dir)

    def init_config(self):
        from config_manager import AppConfigManager
        prompt_dir = get_resource_path('prompts')
        self.config_manager = AppConfigManager(self.config_db_path)
        self.config_manager.seed_defaults(prompt_dir)
        logger.info("配置管理器初始化完成")

        from knowledge_base import KnowledgeManager, KnowledgeRetriever
        config = self.config_manager.get_config()
        # 必须先注入 DB_PATH，KnowledgeManager/KnowledgeRetriever 构造函数会直接访问 config["DB_PATH"]
        config["DB_PATH"] = self.config_manager.db_path
        self.knowledge_manager = KnowledgeManager(config)
        self.knowledge_retriever = KnowledgeRetriever(config)

    def build_live_instance(self):
        """Instantiate XianyuLive and XianyuReplyBot from current DB config."""
        from config_manager import AppConfigManager
        from main import XianyuLive
        from XianyuAgent import XianyuReplyBot
        from context_manager import ChatContextManager

        config = self.config_manager.get_config()
        prompt_overrides = self.config_manager.get_all_prompts()

        cookies_str = config.get("COOKIES_STR", "")
        if not cookies_str:
            raise ValueError("COOKIES_STR 未配置，请在设置页面填写 Cookie")

        if not config.get("API_KEY", ""):
            raise ValueError("API_KEY 未配置，请在设置页面填写 API Key")

        bot = XianyuReplyBot(config=config, prompt_overrides=prompt_overrides)
        context_manager = ChatContextManager(db_path=self.chat_db_path)
        live = XianyuLive(
            cookies_str=cookies_str,
            config=config,
            config_manager=self.config_manager
        )
        live.set_context_manager(context_manager)
        live.set_bot(bot)
        return live

    async def start_bot(self):
        if self.bot_task and not self.bot_task.done():
            logger.warning("机器人已在运行中")
            return

        try:
            logger.info("正在启动机器人...")

            # --- Always refresh cookies via CDP before starting ---
            from login_browser import browser_login
            logger.info("正在通过 CDP 浏览器刷新 Cookie…")
            success = await browser_login(self.config_manager)
            if not success:
                logger.error("CDP 登录失败，机器人未启动。请重试。")
                emit_status(False)
                return
            logger.info("CDP 登录成功，继续启动机器人")

            live = self.build_live_instance()
            self.bot_task = asyncio.create_task(live.main())
            emit_status(True)
            logger.info("机器人已启动")

            # Wait for task and handle completion / errors
            try:
                await self.bot_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"机器人运行异常: {e}")
                emit_error("BOT_ERROR", str(e))
            finally:
                emit_status(False)
                logger.info("机器人已停止")

        except Exception as e:
            logger.error(f"机器人启动失败: {e}")
            emit_error("START_FAILED", str(e))
            emit_status(False)

    async def stop_bot(self):
        if not self.bot_task or self.bot_task.done():
            emit_status(False)
            return

        logger.info("正在停止机器人...")
        self.bot_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(self.bot_task), timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        emit_status(False)
        logger.info("机器人已停止")

    async def handle_generate_prompts(self, chat_log: str):
        logger.info("正在调用 AI 分析聊天记录，生成提示词…")
        try:
            from openai import AsyncOpenAI
            config = self.config_manager.get_config()
            client = AsyncOpenAI(
                api_key=config.get("API_KEY", ""),
                base_url=config.get("MODEL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            )
            model = config.get("MODEL_NAME", "qwen-max")

            system_prompt = (
                "你是一个咸鱼（闲鱼）智能客服提示词生成专家。\n"
                "用户会提供一段买卖双方的聊天记录。\n"
                "请根据聊天记录中卖家的回复风格、议价策略和专业知识，"
                "为以下 4 个角色分别生成一段高质量的系统提示词（system prompt）：\n"
                "1. classify_prompt：意图分类 Agent，判断用户消息属于 price/tech/default 哪种意图\n"
                "2. price_prompt：价格谈判 Agent，负责礼貌但坚定地处理砍价\n"
                "3. tech_prompt：技术咨询 Agent，负责回答商品的技术/使用问题\n"
                "4. default_prompt：默认回复 Agent，处理其他通用咨询\n\n"
                "输出格式必须严格为如下 JSON（不要包含任何其他文字）：\n"
                '{"classify_prompt": "...", "price_prompt": "...", "tech_prompt": "...", "default_prompt": "..."}'
            )

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"以下是聊天记录：\n\n{chat_log}"},
                ],
                temperature=0.5,
                max_tokens=2000,
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                lines = raw.splitlines()
                # Remove opening fence line (```json or ```)
                lines = lines[1:]
                # Remove closing fence line if present
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
            prompts = json.loads(raw)

            required = {"classify_prompt", "price_prompt", "tech_prompt", "default_prompt"}
            if not required.issubset(prompts.keys()):
                raise ValueError(f"AI 返回字段缺失: {required - prompts.keys()}")

            logger.info("AI 提示词生成成功")
            emit_generate_prompts_result(True, prompts)

        except Exception as e:
            logger.error(f"AI 提示词生成失败: {e}")
            emit_generate_prompts_result(False, message=str(e))

    async def run(self):
        loop = asyncio.get_running_loop()
        cmd_queue: asyncio.Queue = asyncio.Queue()

        # Start stdin reader thread
        t = threading.Thread(target=stdin_thread, args=(cmd_queue, loop), daemon=True)
        t.start()

        logger.info("Bridge 已就绪，等待指令...")
        emit_status(False)

        # Command dispatch loop
        start_task = None

        while True:
            try:
                cmd = await asyncio.wait_for(cmd_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            action = cmd.get("cmd", "")

            if action == "start":
                if start_task and not start_task.done():
                    logger.warning("机器人已在运行中，忽略重复 start 命令")
                else:
                    start_task = asyncio.create_task(self.start_bot())

            elif action == "stop":
                if start_task and not start_task.done():
                    start_task.cancel()
                    try:
                        await asyncio.wait_for(asyncio.shield(start_task), timeout=6.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                await self.stop_bot()
                start_task = None

            elif action == "reload_config":
                logger.info("收到 reload_config 指令，重新加载配置...")
                was_running = start_task and not start_task.done()
                # Stop first
                if was_running:
                    start_task.cancel()
                    try:
                        await asyncio.wait_for(asyncio.shield(start_task), timeout=6.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                await self.stop_bot()
                start_task = None
                # Reload config from DB, restart only if was running before
                self.init_config()
                if was_running:
                    start_task = asyncio.create_task(self.start_bot())

            elif action == "generate_prompts":
                chat_log = cmd.get("chat_log", "")
                if not chat_log.strip():
                    emit_generate_prompts_result(False, message="聊天记录不能为空")
                elif not self.generate_task or self.generate_task.done():
                    self.generate_task = asyncio.create_task(
                        self.handle_generate_prompts(chat_log)
                    )
                else:
                    logger.warning("AI 生成已在进行中，忽略重复请求")

            elif action == "knowledge:rebuild_index":
                if not self.knowledge_task or self.knowledge_task.done():
                    self.knowledge_task = asyncio.create_task(
                        self._handle_rebuild_index()
                    )
                else:
                    logger.debug("[knowledge] 索引重建已在进行中，忽略重复请求")

            elif action == "knowledge:generate_from_image":
                image_path = cmd.get("image_path", "")
                if not image_path:
                    self._emit_knowledge_error("image_path 不能为空")
                elif not self.knowledge_task or self.knowledge_task.done():
                    self.knowledge_task = asyncio.create_task(
                        self._handle_generate_from_image(image_path)
                    )
                else:
                    self._emit_knowledge_error("AI 生成已在进行中，请稍后再试")

            elif action == "knowledge:generate_from_chat":
                chat_text = cmd.get("chat_text", "")
                if not chat_text.strip():
                    self._emit_knowledge_error("聊天记录不能为空")
                elif not self.knowledge_task or self.knowledge_task.done():
                    self.knowledge_task = asyncio.create_task(
                        self._handle_generate_from_chat(chat_text)
                    )
                else:
                    self._emit_knowledge_error("AI 生成已在进行中，请稍后再试")

            else:
                logger.warning(f"未知命令: {action}")


    def _emit_knowledge_error(self, message: str):
        payload = {"type": "knowledge_generate_error", "message": message}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    async def _handle_rebuild_index(self):
        try:
            await self.knowledge_manager.rebuild_index()
            self.knowledge_retriever.invalidate_cache()
            sys.stdout.write(json.dumps({"type": "knowledge_rebuild_result", "success": True}) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"[knowledge] 索引重建失败: {e}")

    async def _handle_generate_from_image(self, image_path: str):
        try:
            result = await self.knowledge_manager.generate_from_image(image_path)
            payload = {"type": "knowledge_generate_result", "data": result}
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"[knowledge] 图片生成 Q&A 失败: {e}")
            self._emit_knowledge_error(str(e))

    async def _handle_generate_from_chat(self, chat_text: str):
        try:
            result = await self.knowledge_manager.generate_from_chat_log(chat_text)
            payload = {"type": "knowledge_generate_result", "data": result}
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"[knowledge] 聊天记录生成 Q&A 失败: {e}")
            self._emit_knowledge_error(str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Set BRIDGE_MODE env so downstream code knows it's running under Electron
    os.environ['BRIDGE_MODE'] = '1'

    # Setup loguru: remove default stderr handler, add JSON stdout sink + file sink
    logger.remove()
    logger.add(stdout_json_sink, level="DEBUG")

    # File sink: rotate daily, keep 7 days, UTF-8, stored in %APPDATA%\XianyuAutoAgent\logs\
    log_dir = os.path.join(get_data_dir(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    logger.add(
        os.path.join(log_dir, '{time:YYYY-MM-DD}.log'),
        level="DEBUG",
        encoding="utf-8",
        rotation="00:00",       # new file each day at midnight
        retention="7 days",     # keep logs for 7 days
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
        enqueue=True,           # thread-safe async write
    )

    data_dir = get_data_dir()
    manager = BridgeManager(data_dir)
    manager.load_modules()
    manager.init_config()

    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
