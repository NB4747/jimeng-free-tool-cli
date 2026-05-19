import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


async def download_image(url: str, save_path: str) -> bool:
    """Download an image from *url* and save it to *save_path*.

    Returns True on success, False on failure.
    """
    try:
        save_path = os.path.abspath(save_path)
        Path(os.path.dirname(save_path)).mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(save_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        f.write(chunk)

        logger.info("Image downloaded successfully → %s", save_path)
        return True

    except httpx.TimeoutException:
        logger.error("Download timed out for URL: %s", url)
        return False
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error %d while downloading %s", e.response.status_code, url)
        return False
    except OSError as e:
        logger.error("File-system error writing to %s: %s", save_path, e)
        return False
    except Exception:
        logger.exception("Unexpected error downloading image from %s", url)
        return False
