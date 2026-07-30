import asyncio
from contextlib import suppress

from playwright.async_api import Browser, Playwright, async_playwright


class BrowserRenderer:
    def __init__(self, max_concurrency: int = 3) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

        self._start_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def start(self) -> None:
        async with self._start_lock:
            if self._browser and self._browser.is_connected():
                return

            if self._browser:
                with suppress(Exception):
                    await self._browser.close()
                self._browser = None

            if self._playwright is None:
                self._playwright = await async_playwright().start()

            self._browser = await self._playwright.chromium.launch(
                headless=True,
            )

    async def screenshot_html(
        self,
        html: str,
        *,
        selector: str,
        viewport_width: int,
        viewport_height: int,
        timeout_ms: int = 10_000,
        omit_background: bool = False,
    ) -> bytes:
        async with self._semaphore:
            await self.start()

            browser = self._browser
            if browser is None:
                raise RuntimeError("Chromium failed to start")

            context = await browser.new_context(
                viewport={
                    "width": viewport_width,
                    "height": viewport_height,
                },
                device_scale_factor=1,
            )

            try:
                page = await context.new_page()
                page.set_default_timeout(timeout_ms)

                await page.set_content(html, wait_until="load")

                # Wait for custom fonts and inline emoji images.
                await page.evaluate("() => document.fonts.ready")
                await page.wait_for_function(
                    """() => Array.from(document.images)
                        .every(image => image.complete)"""
                )
                await page.wait_for_selector("body.ready")

                element = page.locator(selector)
                await element.wait_for(state="visible")

                return await element.screenshot(
                    type="png",
                    animations="disabled",
                    omit_background=omit_background,
                )
            finally:
                with suppress(Exception):
                    await context.close()

    async def close(self) -> None:
        async with self._start_lock:
            if self._browser:
                with suppress(Exception):
                    await self._browser.close()
                self._browser = None

            if self._playwright:
                with suppress(Exception):
                    await self._playwright.stop()
                self._playwright = None
