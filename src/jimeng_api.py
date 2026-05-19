"""Direct Jimeng REST API client — no browser needed.

Based on the official Jimeng API structure reverse-engineered from
jimeng-free-api-all (thanks to LLM-Red-Team / zhizinan1997).

Allows pure-headless image generation via cookie + HTTP requests,
bypassing the Playwright browser automation entirely.
"""

import hashlib
import json
import logging
import math
import random
import re
import string
import time
import uuid
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

DEFAULT_ASSISTANT_ID = 513695
DRAFT_VERSION = "3.3.8"
VERSION_CODE = "5.8.0"
PLATFORM_CODE = "7"

DEFAULT_MODEL = "jimeng-image-4.5"

MODEL_MAP = {
    "jimeng-image-4.5": "high_aes_general_v40l",
    "jimeng-image-4.1": "high_aes_general_v41",
    "jimeng-image-4.0": "high_aes_general_v40",
    "jimeng-image-3.1": "high_aes_general_v30l_art_fangzhou:general_v3.0_18b",
    "jimeng-image-3.0": "high_aes_general_v30l:general_v3.0_18b",
    "jimeng-image-2.0-pro": "high_aes_general_v20_L:general_v2.0_L",
}

ASPECT_RATIOS: dict[str, int] = {
    "21:9": 0, "16:9": 1, "3:2": 2, "4:3": 3,
    "1:1": 8, "3:4": 4, "2:3": 5, "9:16": 6,
}

DIMENSIONS_1K: dict[str, tuple[int, int]] = {
    "21:9": (2016, 846), "16:9": (1664, 936), "3:2": (1584, 1056),
    "4:3": (1472, 1104), "1:1": (1328, 1328), "3:4": (1104, 1472),
    "2:3": (1056, 1584), "9:16": (936, 1664),
}

DIMENSIONS_2K: dict[str, tuple[int, int]] = {
    "21:9": (3024, 1296), "16:9": (2560, 1440), "3:2": (2496, 1664),
    "4:3": (2304, 1728), "1:1": (2048, 2048), "3:4": (1728, 2304),
    "2:3": (1664, 2496), "9:16": (1440, 2560),
}

FAKE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Appid": str(DEFAULT_ASSISTANT_ID),
    "Appvr": VERSION_CODE,
    "Origin": "https://jimeng.jianying.com",
    "Pf": PLATFORM_CODE,
    "Referer": "https://jimeng.jianying.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
}

PROCESSING_STATES = {20, 42, 45}
FAIL_STATE = 30


# ------------------------------------------------------------------
# Client
# ------------------------------------------------------------------


class JiMengAPIError(Exception):
    """Raised when the Jimeng API returns an error."""


class InsufficientCreditsError(JiMengAPIError):
    """Not enough credits."""


class ContentFilteredError(JiMengAPIError):
    """Prompt flagged by content filter."""


class JiMengAPIClient:
    """Direct Jimeng API client — uses session cookie, no browser."""

    def __init__(self, cookie: str, model: str = DEFAULT_MODEL):
        self._cookie = cookie
        self._model = model
        self._device_id = str(random.randint(7_000_000_000_000_000_000, 9_999_999_999_999_999_999))
        self._web_id = str(random.randint(7_000_000_000_000_000_000, 9_999_999_999_999_999_999))
        self._user_id = uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        ratio: str = "1:1",
        resolution: str = "2k",
        negative_prompt: str = "",
        sample_strength: float = 0.5,
    ) -> str:
        """Generate an image and return the image URL.

        Raises JiMengAPIError / InsufficientCreditsError / ContentFilteredError.
        """
        # Detect ratio from prompt
        detected = self._detect_aspect_ratio(prompt)
        if detected and ratio == "1:1":
            ratio = detected

        internal_model = MODEL_MAP.get(self._model, MODEL_MAP[DEFAULT_MODEL])
        is_4x = self._model in (
            "jimeng-image-4.5", "jimeng-image-4.1", "jimeng-image-4.0",
        )
        resolution = resolution if resolution in ("1k", "2k") else ("2k" if is_4x else "1k")
        dims = DIMENSIONS_2K[ratio] if resolution == "2k" else DIMENSIONS_1K[ratio]
        width, height = dims
        image_ratio = ASPECT_RATIOS[ratio]

        # Check credits
        await self._ensure_credits()

        component_id = uuid.uuid4().hex
        submit_id = uuid.uuid4().hex

        abilities = {
            "type": "",
            "id": uuid.uuid4().hex,
            "generate": {
                "type": "",
                "id": uuid.uuid4().hex,
                "core_param": {
                    "type": "",
                    "id": uuid.uuid4().hex,
                    "model": internal_model,
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "seed": math.floor(random.random() * 100_000_000) + 2_500_000_000,
                    "sample_strength": sample_strength,
                    "image_ratio": image_ratio,
                    "large_image_info": {
                        "type": "",
                        "id": uuid.uuid4().hex,
                        "height": height,
                        "width": width,
                        "resolution_type": resolution,
                    },
                },
                "history_option": {"type": "", "id": uuid.uuid4().hex},
            },
        }

        request_data = {
            "extend": {"root_model": internal_model},
            "submit_id": submit_id,
            "metrics_extra": json.dumps({
                "promptSource": "custom",
                "generateCount": 1,
                "enterFrom": "click",
                "sceneOptions": json.dumps([{
                    "type": "image",
                    "scene": "ImageBasicGenerate",
                    "modelReqKey": internal_model,
                    "resolutionType": resolution,
                    "abilityList": [],
                    "benefitCount": 4 if (is_4x and resolution == "2k") else 1,
                    "reportParams": {
                        "enterSource": "generate",
                        "vipSource": "generate",
                        "extraVipFunctionKey": f"{internal_model}-{resolution}",
                        "useVipFunctionDetailsReporterHoc": True,
                    },
                }]),
                "isBoxSelect": False,
                "isCutout": False,
                "generateId": submit_id,
                "isRegenerate": False,
            }),
            "draft_content": json.dumps({
                "type": "draft",
                "id": uuid.uuid4().hex,
                "min_version": "3.0.2",
                "min_features": [],
                "is_from_tsn": True,
                "version": DRAFT_VERSION,
                "main_component_id": component_id,
                "component_list": [{
                    "type": "image_base_component",
                    "id": component_id,
                    "min_version": "3.0.2",
                    "metadata": {
                        "type": "",
                        "id": uuid.uuid4().hex,
                        "created_platform": 3,
                        "created_platform_version": "",
                        "created_time_in_ms": str(int(time.time() * 1000)),
                        "created_did": "",
                    },
                    "generate_type": "generate",
                    "aigc_mode": "workbench",
                    "abilities": abilities,
                }],
            }),
            "http_common_info": {"aid": DEFAULT_ASSISTANT_ID},
        }

        logger.info(
            "API generate: model=%s ratio=%s resolution=%s size=%dx%d",
            self._model, ratio, resolution, width, height,
        )

        result = await self._request(
            "POST", "/mweb/v1/aigc_draft/generate",
            params={
                "da_version": DRAFT_VERSION,
                "web_component_open_flag": 1,
                "web_version": DRAFT_VERSION,
            },
            data=request_data,
        )
        aigc_data = result.get("aigc_data", result)
        history_id = aigc_data.get("history_record_id")
        if not history_id:
            raise JiMengAPIError("No history_record_id in response")

        # Poll for result
        return await self._poll_result(history_id, width, height)

    async def get_credits(self) -> dict:
        """Return credit info."""
        data = await self._request(
            "POST", "/commerce/v1/benefits/user_credit", data={}
        )
        credit = data.get("credit", data)
        return {
            "gift": credit.get("gift_credit", 0),
            "purchase": credit.get("purchase_credit", 0),
            "vip": credit.get("vip_credit", 0),
            "total": sum((
                credit.get("gift_credit", 0),
                credit.get("purchase_credit", 0),
                credit.get("vip_credit", 0),
            )),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _generate_cookie(self) -> str:
        ts = int(time.time())
        parts = [
            f"_tea_web_id={self._web_id}",
            "is_staff_user=false",
            "store-region=cn-gd",
            "store-region-src=uid",
            f"sid_guard={self._cookie}%7C{ts}%7C5184000%7CMon%2C+03-Feb-2025+08%3A17%3A09+GMT",
            f"uid_tt={self._user_id}",
            f"uid_tt_ss={self._user_id}",
            f"sid_tt={self._cookie}",
            f"sessionid={self._cookie}",
            f"sessionid_ss={self._cookie}",
        ]
        return "; ".join(parts)

    def _generate_sign(self, uri: str) -> str:
        device_time = str(int(time.time()))
        raw = f"9e2c|{uri[-7:]}|{PLATFORM_CODE}|{VERSION_CODE}|{device_time}||11ac"
        return hashlib.md5(raw.encode()).hexdigest()

    async def _request(
        self, method: str, uri: str, params=None, data=None
    ) -> dict:
        device_time = str(int(time.time()))
        sign = self._generate_sign(uri)
        headers = {
            **FAKE_HEADERS,
            "Cookie": self._generate_cookie(),
            "Device-Time": device_time,
            "Sign": sign,
            "Sign-Ver": "1",
        }

        url = f"https://jimeng.jianying.com{uri}"
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.request(
                method, url,
                params={**({"aid": DEFAULT_ASSISTANT_ID, "device_platform": "web", "region": "CN", "webId": self._web_id}), **(params or {})},
                json=data,
                headers=headers,
            )
        body = resp.json()
        ret = body.get("ret", -1)
        if str(ret) != "0":
            errmsg = body.get("errmsg", "unknown")
            logger.error("API error ret=%s: %s", ret, errmsg)
            if str(ret) in ("5000", "1006"):
                raise InsufficientCreditsError(errmsg)
            raise JiMengAPIError(f"[{ret}] {errmsg}")
        return body.get("data", body)

    async def _ensure_credits(self):
        credits = await self.get_credits()
        logger.info("Credits: total=%d", credits["total"])
        if credits["total"] <= 0:
            logger.info("Attempting to receive daily credits …")
            await self._receive_credits()

    async def _receive_credits(self):
        await self._request(
            "POST", "/commerce/v1/benefits/credit_receive",
            data={"time_zone": "Asia/Shanghai"},
        )
        logger.info("Daily credits received.")

    async def _poll_result(
        self, history_id: str, width: int, height: int
    ) -> str:
        for attempt in range(120):
            await self._sleep(1.0)
            result = await self._request(
                "POST", "/mweb/v1/get_history_by_ids",
                data={
                    "history_ids": [history_id],
                    "image_info": {
                        "width": width, "height": height,
                        "format": "webp",
                        "image_scene_list": [
                            {"scene": "normal", "width": 2400, "height": 2400, "uniq_key": "2400", "format": "webp"},
                            {"scene": "normal", "width": 1080, "height": 1080, "uniq_key": "1080", "format": "webp"},
                        ],
                    },
                    "http_common_info": {"aid": DEFAULT_ASSISTANT_ID},
                },
            )
            entry = result.get(history_id, {})
            status = entry.get("status", 20)
            fail_code = entry.get("fail_code", "")

            if status == FAIL_STATE:
                if fail_code == "2038":
                    raise ContentFilteredError("Content filtered")
                raise JiMengAPIError(f"Generation failed: status={status} fail_code={fail_code}")

            item_list = entry.get("item_list") or []
            if item_list:
                url = self._extract_url(item_list[0])
                if url:
                    logger.info("Image URL obtained (attempt %d): %s", attempt + 1, url[:120])
                    return url

            if status not in PROCESSING_STATES and item_list:
                url = self._extract_url(item_list[0])
                if url:
                    return url

        raise JiMengAPIError("Image generation timed out after 120s")

    @staticmethod
    def _extract_url(item: dict) -> Optional[str]:
        """Extract image URL from API response item.

        Priority:
        1. large_images[0].image_url (original / highest resolution)
        2. common_attr.cover_url (fallback)
        """
        try:
            large = item.get("image", {}).get("large_images", [])
            if large and large[0].get("image_url"):
                return large[0]["image_url"]
        except Exception:
            pass
        try:
            cover = item.get("common_attr", {}).get("cover_url")
            if cover:
                return cover
        except Exception:
            pass
        return None

    @staticmethod
    def _detect_aspect_ratio(prompt: str) -> Optional[str]:
        """Detect aspect ratio from prompt keywords."""
        m = re.search(r"(\d+)\s*[:：]\s*(\d+)", prompt)
        if m:
            key = f"{m.group(1)}:{m.group(2)}"
            if key in ASPECT_RATIOS:
                return key
        if re.search(r"横屏|横版|宽屏", prompt):
            return "16:9"
        if re.search(r"竖屏|竖版|手机", prompt):
            return "9:16"
        if re.search(r"方形|正方", prompt):
            return "1:1"
        return None

    @staticmethod
    async def _sleep(seconds: float):
        import asyncio
        await asyncio.sleep(seconds)
