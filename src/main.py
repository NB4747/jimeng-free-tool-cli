import logging
import os

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


@mcp.tool()
async def generate_game_asset(prompt: str, output_path: str | None = None) -> str:
    """Generate an image on jimeng.jianying.com and download it locally.

    Args:
        prompt: The text-to-image prompt (required).
        output_path: Where to save the image (file path or directory).
                     Defaults to ./downloads/<safe_prompt>.png.
    """
    cdp_url = _config.get("cdp_url", "http://localhost:9222")
    task_timeout = _config.get("task_timeout", 60)

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


if __name__ == "__main__":
    mcp.run()
