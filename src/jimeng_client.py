import asyncio
import json
import logging
import os
import re
from typing import Optional

from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)


class AuthRequiredException(Exception):
    """Raised when the user is not logged in to jimeng.jianying.com."""


class JiMengClient:
    """Headless control of a Chrome instance via CDP for text-to-image
    generation on jimeng.jianying.com."""

    _JIMENG_DOMAIN = "jimeng.jianying.com"
    _AUTH_SELECTORS = [
        'text="登录"',
        'text="注册"',
        'text="请登录"',
        'button:has-text("登录")',
        'a:has-text("登录")',
    ]
    # ProseMirror rich-text editor
    _EDITOR_SELECTOR = ".tiptap.ProseMirror[contenteditable=\"true\"]"
    # Submit button (becomes enabled once text is entered)
    _SUBMIT_SELECTOR = ".submit-button-wD1gIc"
    # Mode dropdown: switch to "图片生成"
    _MODE_SELECT_SELECTOR = ".toolbar-select-DS5gGq"
    _MODE_TARGET_TEXT = "图片生成"

    def __init__(
        self,
        cdp_url: str = "http://localhost:9222",
        api_url_patterns: Optional[list[str]] = None,
        task_timeout: float = 60.0,
        poll_interval: float = 1.0,
    ):
        self._cdp_url = cdp_url
        self._api_patterns = api_url_patterns or [
            r"api/v1/task",
            r"text2img/action",
            r"api/task",
            r"aigc_dream",
            r"aigc/v1",
            r"mweb/v1",
            r"dreamina",
        ]
        self._task_timeout = task_timeout
        self._poll_interval = poll_interval

        # Runtime state
        self._captured_image_url: Optional[str] = None
        self._url_event: Optional[asyncio.Event] = None
        self._browser = None
        self._context = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, prompt: str) -> str:
        """Run the full text-to-image flow and return the image URL.

        Raises AuthRequiredException when the user needs to log in.
        """
        self._captured_image_url = None
        self._url_event = asyncio.Event()

        try:
            await self._connect()
            await self._navigate_to_jimeng()
            await self._check_auth()
            await self._attach_network_listener()
            await self._ensure_image_gen_mode()
            await self._fill_prompt(prompt)
            await self._wait_for_submit_enabled()
            await self._click_generate()
            image_url = await self._wait_for_image_url()
            return image_url
        finally:
            self._url_event = None

    async def close(self):
        """Dispose Playwright resources (keep the browser open)."""
        if self._context:
            # We don't close the browser — the user owns the process.
            pass
        self._page = None
        self._context = None
        self._browser = None

    # ------------------------------------------------------------------
    # Internal: connection & navigation
    # ------------------------------------------------------------------

    async def _connect(self):
        logger.info("Connecting to Chrome CDP at %s", self._cdp_url)
        try:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.connect_over_cdp(self._cdp_url)
        except Exception as exc:
            raise RuntimeError(
                "Cannot connect to Chrome at %s. "
                "Is it running with --remote-debugging-port?"
                % self._cdp_url
            ) from exc

    async def _navigate_to_jimeng(self):
        """Reuse an existing jimeng tab, navigating to the home page."""
        self._context = self._browser.contexts[0]
        for page in self._context.pages:
            if self._JIMENG_DOMAIN in (page.url or ""):
                logger.info("Reusing existing jimeng tab: %s", page.url)
                await page.bring_to_front()
                # Always navigate to home for a consistent start
                if "/ai-tool/home/" not in (page.url or ""):
                    await page.goto(
                        "https://jimeng.jianying.com/ai-tool/home/",
                        wait_until="domcontentloaded",
                    )
                    await page.wait_for_timeout(2000)
                self._page = page
                return

        logger.info("Opening new jimeng tab …")
        self._page = await self._context.new_page()
        await self._page.goto("https://jimeng.jianying.com/ai-tool/home/", wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # Internal: auth check
    # ------------------------------------------------------------------

    async def _check_auth(self):
        for selector in self._AUTH_SELECTORS:
            try:
                el = await self._page.wait_for_selector(
                    selector, timeout=3000, state="attached"
                )
                if el:
                    raise AuthRequiredException(
                        "登录状态已失效，请在 Chrome 中完成扫码登录后重试。"
                    )
            except AuthRequiredException:
                raise
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Internal: network interception
    # ------------------------------------------------------------------

    async def _attach_network_listener(self):
        compiled = [re.compile(p, re.IGNORECASE) for p in self._api_patterns]

        async def _on_response(response):
            url = response.url
            # Quick filter: skip obvious static resources
            if any(x in url for x in (".js", ".css", ".svg", ".ico", ".woff", ".png", ".jpg", ".webp")):
                return
            # Match API patterns OR look for JSON with dreamina in URL
            matches = any(p.search(url) for p in compiled)
            if not matches and "dreamina" not in url and "aigc" not in url:
                return
            try:
                body = await response.json()
            except Exception:
                return

            logger.info("Intercepted API response: %s", url)
            image_url = self._extract_image_url(body)
            if image_url:
                logger.info("Captured image URL via API: %s", image_url[:150])
                self._captured_image_url = image_url
                if self._url_event:
                    self._url_event.set()
            else:
                # Log the response body for debugging
                body_str = json.dumps(body, ensure_ascii=False)[:500]
                logger.debug("API response without image URL: %s", body_str)

        self._page.on("response", _on_response)

    @staticmethod
    def _extract_image_url(body) -> Optional[str]:
        """Walk common JSON shapes to find an image URL."""
        candidates = [
            # data.image_url
            (lambda b: isinstance(b, dict) and b.get("data", {}).get("image_url")),
            # data.result.image_url
            (lambda b: isinstance(b, dict)
             and isinstance(b.get("data"), dict)
             and b["data"].get("result", {}).get("image_url")),
            # response.items[0].url
            (lambda b: isinstance(b, dict)
             and isinstance(b.get("response"), dict)
             and isinstance(b["response"].get("items"), list)
             and len(b["response"]["items"]) > 0
             and b["response"]["items"][0].get("url")),
            # data.images[0].url
            (lambda b: isinstance(b, dict)
             and isinstance(b.get("data"), dict)
             and isinstance(b["data"].get("images"), list)
             and len(b["data"]["images"]) > 0
             and b["data"]["images"][0].get("url")),
            # bare "url" key at any level (last resort)
            (lambda b: isinstance(b, dict) and b.get("url") if isinstance(b.get("url"), str) and b["url"].startswith("http") else None),
        ]

        for fn in candidates:
            try:
                result = fn(body)
                if result:
                    return result
            except Exception:
                continue

        # Deep walk: find all dreamina URLs, prefer original resolution
        def _deep_search(obj, depth=0, found=None):
            if found is None:
                found = []
            if depth > 10:
                return found
            if isinstance(obj, str):
                if ("dreamina-sign" in obj or ("byteimg.com" in obj and "tos-cn-i" in obj)) and obj.startswith("http"):
                    found.append(obj)
            if isinstance(obj, dict):
                for v in obj.values():
                    _deep_search(v, depth + 1, found)
            if isinstance(obj, list):
                for item in obj:
                    _deep_search(item, depth + 1, found)
            return found

        urls = _deep_search(body)
        if not urls:
            return None
        # Prefer original size (resize:0:0 or no resize suffix)
        for url in urls:
            if "resize:0:0" in url or "resize%3A0%3A0" in url:
                return url
        # Prefer larger thumbnails
        for url in urls:
            if "aigc_resize_loss" in url:
                return url  # lossless resize
        return urls[0]

    # ------------------------------------------------------------------
    # Internal: UI interaction
    # ------------------------------------------------------------------

    async def _ensure_image_gen_mode(self):
        """Switch mode dropdown to '图片生成' if not already selected."""
        logger.info("Checking mode selector …")
        # The mode switcher is a combobox showing current mode (Agent 模式 by default)
        # Find it by looking for the visible .lv-select-view-value containing "Agent" or "图片"
        mode_selects = self._page.locator(".lv-select-view-value")
        target_select = None
        for i in range(await mode_selects.count()):
            el = mode_selects.nth(i)
            if not await el.is_visible():
                continue
            text = (await el.text_content() or "").strip()
            if "Agent" in text or "图片生成" in text or "视频生成" in text:
                target_select = el
                break
        if target_select is None:
            logger.info("Mode selector not found, proceeding anyway.")
            return
        current = (await target_select.text_content() or "").strip()
        if self._MODE_TARGET_TEXT in current:
            logger.info("Already in 图片生成 mode.")
            return
        # Click to open the dropdown
        logger.info("Switching mode from '%s' to 图片生成 …", current)
        await target_select.click()
        await self._page.wait_for_timeout(800)
        # Look for the option in popup
        popup = self._page.locator('[class*="select-popup"]').first
        option = popup.get_by_text(self._MODE_TARGET_TEXT, exact=True)
        try:
            await option.wait_for(state="visible", timeout=3000)
            await option.click()
            logger.info("Mode switched to 图片生成.")
        except Exception:
            # Try clicking any visible element with the text
            options = self._page.get_by_text(self._MODE_TARGET_TEXT, exact=True)
            for j in range(await options.count()):
                opt = options.nth(j)
                if await opt.is_visible():
                    await opt.click()
                    logger.info("Mode switched to 图片生成.")
                    return
            logger.warning("Could not find 图片生成 option.")

    async def _wait_for_submit_enabled(self):
        """Wait until the submit button becomes enabled."""
        logger.info("Waiting for submit button to enable …")
        submit_btn = self._page.locator(self._SUBMIT_SELECTOR).first
        for _ in range(20):
            disabled = await submit_btn.get_attribute("disabled")
            if disabled is None:
                logger.info("Submit button enabled.")
                return
            await self._page.wait_for_timeout(500)
        logger.warning("Submit button still disabled after waiting.")

    async def _fill_prompt(self, prompt: str):
        logger.info("Filling prompt …")
        # ProseMirror tip-tap editor: find the visible contenteditable div
        editors = self._page.locator(self._EDITOR_SELECTOR)
        count = await editors.count()
        for i in range(count):
            editor = editors.nth(i)
            if await editor.is_visible():
                await editor.click()
                await self._page.wait_for_timeout(300)
                # Clear any existing content and type the prompt
                await editor.press("Control+a")
                await editor.press("Backspace")
                await editor.press("Backspace")
                await editor.type(prompt, delay=30)
                logger.info("Prompt filled via ProseMirror editor #%d", i)
                return
        raise RuntimeError("Cannot locate the prompt input box on the page.")

    async def _click_generate(self):
        logger.info("Clicking generate button …")
        submit_btn = self._page.locator(self._SUBMIT_SELECTOR).first
        # Wait until not disabled
        for _ in range(20):
            disabled = await submit_btn.get_attribute("disabled")
            if disabled is None:
                break
            await self._page.wait_for_timeout(500)
        await submit_btn.click()
        logger.info("Generate button clicked.")

    # ------------------------------------------------------------------
    # Internal: polling
    # ------------------------------------------------------------------

    async def _wait_for_image_url(self) -> str:
        """Wait for image URL via network interception, with DOM fallback."""
        logger.info("Waiting for image URL (timeout=%ss) …", self._task_timeout)
        try:
            await asyncio.wait_for(
                self._url_event.wait(), timeout=min(self._task_timeout, 45)
            )
        except asyncio.TimeoutError:
            logger.info("Network interception timed out, trying DOM extraction …")
            image_url = await self._extract_image_from_dom()
            if image_url:
                self._captured_image_url = image_url
            else:
                raise RuntimeError(
                    "Image generation timed out after %ss. "
                    "The task may still be processing on jimeng."
                    % self._task_timeout
                )
        if not self._captured_image_url:
            raise RuntimeError("Failed to capture an image URL.")
        return self._captured_image_url

    async def _extract_image_from_dom(self) -> Optional[str]:
        """After generation, look for result <img> tags on the page."""
        logger.info("Scanning DOM for result images …")
        for _ in range(15):
            await self._page.wait_for_timeout(2000)
            # Look for large images in the result area
            img_urls = await self._page.eval_on_selector_all(
                "img[src*='dreamina-sign']",
                "els => els.filter(el => el.naturalWidth > 200).map(el => el.src)"
            )
            if img_urls:
                # Prefer original size URLs (resize:0:0)
                for url in img_urls:
                    if "resize:0:0" in url or "resize%3A0%3A0" in url:
                        logger.info("Found original-size image: %s", url[:120])
                        return url
                # Fall back to the first image, but try to convert to original
                url = img_urls[0]
                # Replace resize suffixes to get original
                original = re.sub(
                    r'~tplv-[^.]+\.(webp|image)\?.*',
                    r'~tplv-tb4s082cfz-resize:0:0.image',
                    url,
                )
                logger.info("Found image (converted to original): %s", original[:120])
                return original
        return None


# ------------------------------------------------------------------
# Convenience: load config from json
# ------------------------------------------------------------------

def load_config(config_path: str = "config.json") -> dict:
    """Load config.json from the project root (relative to this file)."""
    if not os.path.isabs(config_path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base, config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
