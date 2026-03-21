"""
login_browser.py — Playwright-based browser login for Xianyu.

Opens a visible Chromium window, navigates to the Xianyu homepage, and polls
for the 'unb' cookie that appears after the user completes QR-code login.
On success the full cookie string is persisted via config_manager.
"""

import asyncio


async def browser_login(config_manager) -> bool:
    """
    Launch a headed Chromium browser, wait for the user to scan the login QR
    code, then extract all cookies and save them via config_manager.

    Returns True on success, False on timeout or error.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "playwright 未安装，请执行: pip install playwright && playwright install chromium"
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto("https://www.goofish.com")

            # Poll for the 'unb' cookie (appears after successful login)
            max_wait_seconds = 120
            poll_interval = 2
            elapsed = 0

            while elapsed < max_wait_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                cookies = await context.cookies()
                unb = next((c for c in cookies if c.get("name") == "unb" and c.get("value")), None)

                if unb:
                    # Build "key=value; ..." string from all cookies
                    cookie_str = "; ".join(
                        f"{c['name']}={c['value']}" for c in cookies
                    )
                    config_manager.update_cookies(cookie_str)
                    await browser.close()
                    return True

            # Timed out
            await browser.close()
            return False

    except Exception:
        return False
