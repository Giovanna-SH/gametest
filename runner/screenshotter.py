"""
screenshotter.py — Take screenshots of generated HTML games using Playwright.
Install: pip install playwright && playwright install chromium
"""

import os
import asyncio


async def take_screenshot_async(html_path: str, output_path: str, wait_ms: int = 2000) -> str:
    """Open HTML file in headless browser, wait, and screenshot."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return ""

    abs_html = os.path.abspath(html_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 800, "height": 600})
            await page.goto(f"file://{abs_html}", wait_until="networkidle")
            await page.wait_for_timeout(wait_ms)
            await page.screenshot(path=output_path, full_page=False)
            await browser.close()
        return output_path
    except Exception as e:
        print(f"  [Screenshot Error] {e}")
        return ""


def take_screenshot(html_path: str, output_path: str, wait_ms: int = 2000) -> str:
    """Sync wrapper for the async screenshot function."""
    if not html_path or not os.path.exists(html_path):
        return ""
    return asyncio.run(take_screenshot_async(html_path, output_path, wait_ms))
