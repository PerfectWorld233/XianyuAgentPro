"""
login_browser.py — Pure-CDP browser login for Xianyu (no Playwright).

Launches (or connects to) the user's real Chrome/Edge browser via the
Chrome DevTools Protocol using only the standard `websockets` + `aiohttp`
libraries — no Playwright, no bundled Chromium.

A real browser carries authentic fingerprints (navigator.webdriver stays
false, real plugin list, genuine cna/device cookies, etc.) which avoids
Xianyu's risk-control triggers.

Profile is stored in %APPDATA%\XianyuAutoAgent\browser_profile\ so device
cookies (cna, _uab_uid, …) persist across sessions.

On success the full cookie string is saved via config_manager and the
browser is navigated to the Xianyu messages page (/im).
"""

import asyncio
import json
import os
import socket
import subprocess

import aiohttp
from loguru import logger


REMOTE_DEBUGGING_PORT = 9222
XIANYU_URL = "https://www.goofish.com"
XIANYU_IM_URL = "https://www.goofish.com/im"
CDP_BASE = f"http://localhost:{REMOTE_DEBUGGING_PORT}"

COOKIE_DOMAINS = [
    "goofish.com",
    "taobao.com",
    "alipay.com",
]


def _get_profile_dir() -> str:
    """Return a persistent browser profile directory under %APPDATA%."""
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    profile = os.path.join(base, "XianyuAutoAgent", "browser_profile")
    os.makedirs(profile, exist_ok=True)
    return profile


def _find_browser() -> str:
    """
    Find the path to Chrome or Edge on Windows.
    Chrome is tried first per user request; Edge as fallback.
    Raises RuntimeError if neither browser is found.
    """
    candidates = [
        # Chrome — system-wide
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        # Chrome — per-user
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        # Edge — system-wide
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # Edge — per-user
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            logger.debug(f"找到浏览器: {path}")
            return path
    raise RuntimeError(
        "未找到 Chrome 或 Edge 浏览器，请安装后重试。"
    )


def _is_port_open(port: int) -> bool:
    """Return True if something is already listening on localhost:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _launch_browser(exe: str, profile_dir: str, port: int) -> subprocess.Popen:
    """Start the browser with remote-debugging enabled."""
    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        XIANYU_URL,
    ]
    logger.info(f"启动浏览器: {os.path.basename(exe)}")
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def _get_target_ws_url(session: aiohttp.ClientSession, retries: int = 8, interval: float = 1.0) -> str:
    """
    Poll the CDP /json endpoint until a page target is available.
    Returns the webSocketDebuggerUrl of the first page target.
    """
    for attempt in range(retries):
        try:
            async with session.get(f"{CDP_BASE}/json") as resp:
                targets = await resp.json(content_type=None)
                # Prefer a page that already has our URL, else any page target
                for t in targets:
                    if t.get("type") == "page":
                        return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        if attempt < retries - 1:
            await asyncio.sleep(interval)
    raise RuntimeError(f"无法连接到浏览器调试端口 {REMOTE_DEBUGGING_PORT}，请检查浏览器是否正常启动。")


async def _cdp_call(ws, method: str, params: dict | None = None, msg_id: int = 1) -> dict:
    """Send a CDP command and wait for its matching response."""
    payload = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(payload))
    while True:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("id") == msg_id:
            return msg.get("result", {})


async def _open_new_tab(session: aiohttp.ClientSession) -> str:
    """Open a new tab via CDP /json/new and return its webSocketDebuggerUrl."""
    async with session.get(f"{CDP_BASE}/json/new?{XIANYU_URL}") as resp:
        target = await resp.json(content_type=None)
        return target["webSocketDebuggerUrl"]


async def _get_all_cookies(ws, msg_id_start: int = 10) -> list[dict]:
    """Retrieve all browser cookies via CDP Network.getAllCookies."""
    result = await _cdp_call(ws, "Network.getAllCookies", msg_id=msg_id_start)
    return result.get("cookies", [])


async def browser_login(config_manager) -> bool:
    """
    Connect to (or launch) the user's real Chrome/Edge via pure CDP,
    wait for the user to scan the Xianyu QR code, then extract and
    persist all cookies.

    Returns True on success, False on timeout or error.
    """
    try:
        import aiohttp  # noqa: F401 — already imported at module level, verify available
    except ImportError:
        raise RuntimeError(
            "aiohttp 未安装，请执行: pip install aiohttp"
        )

    profile_dir = _get_profile_dir()

    # Launch the real browser only when the debug port is not yet open
    if not _is_port_open(REMOTE_DEBUGGING_PORT):
        exe = _find_browser()   # raises RuntimeError if not found
        _launch_browser(exe, profile_dir, REMOTE_DEBUGGING_PORT)
        # Give the browser a moment to open its debug server
        await asyncio.sleep(2)
    else:
        logger.debug(f"端口 {REMOTE_DEBUGGING_PORT} 已有浏览器，直接连接")

    try:
        import websockets
    except ImportError:
        raise RuntimeError("websockets 未安装，请执行: pip install websockets")

    try:
        async with aiohttp.ClientSession() as http:
            ws_url = await _get_target_ws_url(http)
            logger.info("已通过 CDP 连接到真实浏览器")

            # Open a new tab and navigate to Xianyu
            new_tab_url = await _open_new_tab(http)

        async with websockets.connect(new_tab_url) as ws:  # type: ignore[attr-defined]
            msg_id = 1

            # Enable the Network domain so we can read cookies
            await _cdp_call(ws, "Network.enable", msg_id=msg_id); msg_id += 1

            # Navigate to Xianyu login page
            await _cdp_call(ws, "Page.navigate", {"url": XIANYU_URL}, msg_id=msg_id); msg_id += 1
            logger.info("已打开闲鱼首页，请在浏览器中扫码登录…")

            # Poll for the 'unb' cookie that appears after successful QR login
            max_wait_seconds = 120
            poll_interval = 2
            elapsed = 0

            while elapsed < max_wait_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                cookies = await _get_all_cookies(ws, msg_id_start=msg_id)
                msg_id += 1

                unb = next(
                    (c for c in cookies
                     if c.get("name") == "unb" and c.get("value")
                     and any(d in c.get("domain", "") for d in COOKIE_DOMAINS)),
                    None,
                )

                if unb:
                    # Filter to relevant domains only
                    relevant = [
                        c for c in cookies
                        if any(d in c.get("domain", "") for d in COOKIE_DOMAINS)
                    ]
                    cookie_str = "; ".join(
                        f"{c['name']}={c['value']}" for c in relevant
                    )
                    config_manager.update_cookies(cookie_str)
                    logger.info("Cookie 已保存，跳转到消息列表页")
                    # Navigate to messages page — leave browser open for the user
                    await _cdp_call(ws, "Page.navigate", {"url": XIANYU_IM_URL}, msg_id=msg_id)
                    return True

            logger.warning("等待登录超时（120 秒）")
            return False

    except Exception as e:
        logger.error(f"CDP 登录异常: {e}")
        return False
