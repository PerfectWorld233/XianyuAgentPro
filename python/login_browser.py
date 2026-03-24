r"""
login_browser.py — CDP-based browser login for Xianyu.

Connects to the user's real Chrome/Edge browser via Chrome DevTools Protocol
using only stdlib (urllib + socket) for HTTP and websockets for WS.
A real browser carries authentic fingerprints which avoids risk-control.

Profile is persisted at %APPDATA%\XianyuAutoAgent\browser_profile\ so device
cookies (cna, _uab_uid, etc.) survive across sessions.
"""

import asyncio
import json
import os
import socket
import subprocess
import urllib.request
import urllib.error

from loguru import logger


REMOTE_DEBUGGING_PORT = 9222
XIANYU_URL = "https://www.goofish.com"
XIANYU_IM_URL = "https://www.goofish.com/im"
CDP_BASE = f"http://localhost:{REMOTE_DEBUGGING_PORT}"
COOKIE_DOMAINS = ["goofish.com", "taobao.com", "alipay.com"]


def _get_profile_dir() -> str:
    """Return a persistent browser profile directory, creating it if needed."""
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    profile = os.path.join(base, "XianyuAutoAgent", "browser_profile")
    try:
        os.makedirs(profile, exist_ok=True)
    except OSError as e:
        logger.warning(f"无法创建浏览器 profile 目录，将不使用持久化 profile: {e}")
        return ""
    return profile


def _find_browser() -> str:
    """
    Find Chrome or Edge on Windows. Chrome is tried first.
    Raises RuntimeError if neither is found.
    """
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            logger.debug(f"找到浏览器: {path}")
            return path
    raise RuntimeError("未找到 Chrome 或 Edge 浏览器，请安装后重试。")


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
        "--no-first-run",
        "--no-default-browser-check",
        XIANYU_URL,
    ]
    if profile_dir:
        args.insert(1, f"--user-data-dir={profile_dir}")
    logger.info(f"启动浏览器: {os.path.basename(exe)}")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
