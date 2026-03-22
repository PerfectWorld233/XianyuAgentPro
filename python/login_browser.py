"""
login_browser.py — CDP-based browser login for Xianyu.

Launches (or connects to) the user's real Chrome/Edge browser via Chrome
DevTools Protocol instead of Playwright's bundled Chromium.  A real browser
carries authentic fingerprints (navigator.webdriver stays false, real plugin
list, genuine cna/device cookies, etc.) which avoids Xianyu's risk-control
triggers caused by automation detection.

Profile is stored in %APPDATA%\XianyuAutoAgent\browser_profile\ so device
cookies (cna, _uab_uid, …) persist across sessions.

On success the full cookie string is saved via config_manager and the browser
is navigated to the Xianyu messages page (/im).
"""

import asyncio
import os
import socket
import subprocess

from loguru import logger


REMOTE_DEBUGGING_PORT = 9222
XIANYU_URL = "https://www.goofish.com"
XIANYU_IM_URL = "https://www.goofish.com/im"


def _get_profile_dir() -> str:
    """Return a persistent browser profile directory under %APPDATA%."""
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    profile = os.path.join(base, "XianyuAutoAgent", "browser_profile")
    os.makedirs(profile, exist_ok=True)
    return profile


def _find_browser() -> str:
    """
    Find the path to Edge or Chrome on Windows.
    Edge is tried first — it ships with every Windows 10/11 installation.
    Raises RuntimeError if neither browser is found.
    """
    candidates = [
        # Edge — system-wide
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # Edge — per-user
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        # Chrome — system-wide
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        # Chrome — per-user
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
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


async def _connect_with_retry(playwright, port: int, retries: int = 6, interval: float = 1.0):
    """Try to connect via CDP, retrying while the browser is still starting up."""
    for attempt in range(retries):
        try:
            return await playwright.chromium.connect_over_cdp(
                f"http://localhost:{port}"
            )
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(interval)
    raise RuntimeError(f"无法连接到浏览器调试端口 {port}，请检查浏览器是否正常启动。")


async def browser_login(config_manager) -> bool:
    """
    Connect to (or launch) the user's real Chrome/Edge via CDP, wait for the
    user to scan the Xianyu QR code, then extract and persist all cookies.

    Returns True on success, False on timeout or error.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "playwright 未安装，请执行: pip install playwright && playwright install chromium"
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

    playwright = await async_playwright().start()
    try:
        browser = await _connect_with_retry(playwright, REMOTE_DEBUGGING_PORT)
        logger.info("已通过 CDP 连接到真实浏览器")

        # Reuse the browser's existing context (carries real cookies / fingerprint)
        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()

        # Open a new tab and navigate to Xianyu
        page = await context.new_page()
        await page.goto(XIANYU_URL)
        logger.info("已打开闲鱼首页，请在浏览器中扫码登录…")

        # Poll for the 'unb' cookie that appears after successful QR login
        max_wait_seconds = 120
        poll_interval = 2
        elapsed = 0

        while elapsed < max_wait_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            cookies = await context.cookies([
                "https://www.goofish.com",
                "https://www.taobao.com",
                "https://www.alipay.com",
            ])
            unb = next(
                (c for c in cookies if c.get("name") == "unb" and c.get("value")),
                None,
            )

            if unb:
                cookie_str = "; ".join(
                    f"{c['name']}={c['value']}" for c in cookies
                )
                config_manager.update_cookies(cookie_str)
                logger.info("Cookie 已保存，跳转到消息列表页")
                # Navigate to messages page — leave browser open for the user
                await page.goto(XIANYU_IM_URL)
                return True

        # Timed out — close the tab we opened, leave the browser running
        logger.warning("等待登录超时（120 秒），已关闭标签页")
        await page.close()
        return False

    except Exception as e:
        logger.error(f"CDP 登录异常: {e}")
        return False

    finally:
        # Disconnect Playwright client — does NOT close the real browser
        try:
            await playwright.stop()
        except Exception:
            pass
