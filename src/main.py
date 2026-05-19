import logging
import os
import subprocess
import sys
import time

import httpx
from mcp.server.fastmcp import FastMCP

from jimeng_client import AuthRequiredException, JiMengClient, load_config
from utils import download_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jimeng_mcp")

mcp = FastMCP("jimeng_tools")
_config = load_config()

# Auth state populated by init_auth_and_chrome()
_auth_state: dict = {}

# ------------------------------------------------------------------
# Auth & Chrome auto-launch
# ------------------------------------------------------------------


def init_auth_and_chrome() -> None:
    """Determine authentication mode and ensure a browser is available.

    Two modes (checked in order):

    1. **Cookie injection mode** (JIMENG_COOKIE env var is set):
       - Headless browser, no window pops up.
       - The cookie value is injected into the browser context so
         jimeng treats the session as already logged-in.

    2. **Auto-hosted Chrome mode** (no JIMENG_COOKIE):
       - Checks whether Chrome is already listening on 9222.
       - If not, searches for chrome.exe in standard Windows paths
         and launches it with --remote-debugging-port=9222, using
         %LOCALAPPDATA%\\jimeng_mcp_chrome_profile as the user-data
         directory, and opens jimeng.jianying.com.
    """
    global _auth_state, _config

    cookie = os.environ.get("JIMENG_COOKIE", "").strip()
    if cookie:
        logger.info("JIMENG_COOKIE found — entering pure-headless cookie mode.")
        _auth_state = {"mode": "cookie", "cookie": cookie, "headless": True}
        _config["headless"] = True
        _config["cookie"] = cookie
        return

    # ---- Auto-hosted Chrome mode ----
    logger.info("No JIMENG_COOKIE; entering auto-hosted Chrome mode …")
    try:
        r = httpx.get("http://127.0.0.1:9222/json/version", timeout=2)
        if r.status_code == 200:
            logger.info("Chrome CDP already listening on 9222.")
            _auth_state = {"mode": "cdp", "headless": False}
            return
    except Exception:
        logger.info("No Chrome on 9222, attempting auto-launch …")

    # Find Chrome
    chrome_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            r"Google\Chrome\Application\chrome.exe",
        ),
        os.path.join(
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            r"Google\Chrome\Application\chrome.exe",
        ),
    ]
    chrome_exe = None
    for path in chrome_candidates:
        if os.path.isfile(path):
            chrome_exe = path
            break
    if not chrome_exe:
        raise RuntimeError(
            "Cannot find Chrome. "
            "Set JIMENG_COOKIE for headless mode, or install Chrome."
        )

    user_data = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "jimeng_mcp_chrome_profile",
    )
    logger.info("Launching: %s", chrome_exe)
    subprocess.Popen(
        [
            chrome_exe,
            "--remote-debugging-port=9222",
            f"--user-data-dir={user_data}",
            "https://jimeng.jianying.com/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    logger.info("Chrome launched — please log in to jimeng if needed.")
    _auth_state = {"mode": "cdp", "headless": False}


# ------------------------------------------------------------------
# MCP Tool
# ------------------------------------------------------------------


@mcp.tool()
async def generate_game_asset(prompt: str, output_path: str | None = None) -> str:
    """Generate an AI image on jimeng.jianying.com（即梦AI）and download it.

    **When to call this tool (CRITICAL):**
    You should invoke this tool automatically whenever the user expresses
    intent to create, generate, or design any kind of image or visual
    asset.  Trigger phrases include (but are not limited to):

      - 画图 / 画画 / 画一个 / 帮我画 …
      - 生成图片 / 生成图像 / 生成一张 / 做一张图 …
      - 创作头像 / 设计头像 / 做一个头像 …
      - 游戏素材 / 游戏背景 / 游戏场景 / 游戏角色 …
      - UI 素材 / 图标 / 插画 / 海报 / 壁纸 …
      - game asset / sprite / background / character art …
      - cyberpunk / fantasy / sci-fi + 图 / 场景 …
      - 任何包含“图片”“图像”“素材”“背景”“头像”“海报”的请求

    **Parameters:**
        prompt (str):
            The image description in natural language.  You should
            write a detailed, vivid prompt that describes the subject,
            style, lighting, composition, colour palette, and mood.
            Write in the same language the user used for their request.
        output_path (str | None):
            Optional save path.  Defaults to ./downloads/<prompt>.png.

    **Returns:**
        A status message with the local file path and the source URL.
    """
    cdp_url = _config.get("cdp_url", "http://localhost:9222")
    task_timeout = _config.get("task_timeout", 60)
    headless = _config.get("headless", False)
    cookie = _config.get("cookie")

    if not output_path:
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in prompt)
        safe_name = safe_name.strip()[:80] or "image"
        output_path = os.path.join(
            _config.get("default_output_dir", "./downloads"),
            safe_name + ".png",
        )

    client = JiMengClient(
        cdp_url=cdp_url,
        api_url_patterns=_config.get("api_patterns"),
        task_timeout=task_timeout,
        poll_interval=_config.get("poll_interval", 1.0),
        headless=headless,
        cookie=cookie,
    )

    try:
        logger.info("Starting image generation for prompt: %s", prompt)
        image_url = await client.generate(prompt)
        logger.info("Image URL obtained: %s", image_url)

        success = await download_image(image_url, output_path)
        if not success:
            return f"【错误】图片下载失败，请检查网络后重试。图片 URL: {image_url}"

        return f"【成功】图片已生成并保存至: {output_path}\n图片 URL: {image_url}"

    except AuthRequiredException:
        if headless:
            return (
                "【错误】Cookie 登录态已失效，请更新 JIMENG_COOKIE 环境变量后重试。"
            )
        return "【错误】您的宿主浏览器即梦登录状态已失效，请在 Chrome 中完成扫码登录后重试。"
    except RuntimeError as e:
        msg = str(e)
        if "Cannot connect to Chrome" in msg:
            return "【错误】无法连接到 Chrome，请确保已通过命令行开启 9222 端口。"
        return f"【错误】{msg}"
    except Exception as e:
        logger.exception("Unexpected error during image generation.")
        return f"【错误】发生未知异常: {e}"
    finally:
        await client.close()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main():
    """Console-script entry point for the jimeng MCP server."""
    init_auth_and_chrome()
    mcp.run()


if __name__ == "__main__":
    main()
