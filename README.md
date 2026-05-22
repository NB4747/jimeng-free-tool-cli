# jimeng-free-tool-cli

> 即梦 AI 免费工具 CLI — 文生图 / 图生图 / 视频生成 / 资产管理一体化命令行工具

无需 API Key，无需付费接口。通过即梦 Cookie 调用官方 REST API，支持 6 款图像模型、5 款视频模型，2K 高清输出，带完整的游戏资产后处理管线。

---

## 目录

- [功能矩阵](#功能矩阵)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [Claude Code MCP 部署](#claude-code-mcp-部署)
- [Python SDK 用法](#python-sdk-用法)
- [游戏资产后处理](#游戏资产后处理)
- [上传引擎](#上传引擎)
- [多账号轮询](#多账号轮询)
- [配置参考](#配置参考)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 功能矩阵

| 能力 | MCP 工具名 | SDK 方法 |
|------|-----------|----------|
| 文生图 | `generate_game_asset` | `client.generate_image()` |
| 图生图 | `generate_image_variation` | `client.generate_image_to_image()` |
| 文生视频 | `generate_video_asset` | `client.generate_video()` |
| 图生视频 | `generate_video_with_frames` | `client.generate_video_with_frames()` |
| 图片上传 | — | `client.upload_image()` |
| 积分查询 | — | `client.get_credits()` |
| 去背 | — | `asset_processor.remove_background()` |
| 缩放 | — | `asset_processor.resize_to_game_standard()` |

### 图像模型

| 模型 | 分辨率 | 说明 |
|------|:------:|------|
| `4.5` | 2K/1K | 最新旗舰，最高质量 |
| `4.1` | 2K/1K | 高质量通用 |
| `4.0` | 2K/1K | 高性能 |
| `3.1` | 1K | 艺术风格增强 |
| `3.0` | 1K | 经济模式（推荐测试用） |
| `2.0-pro` | 1K | 轻量快速 |

### 视频模型

| 模型 | 分辨率 | 时长 |
|------|:------:|:----:|
| `3.0-pro` | 1080p/720p/480p | 5s/10s |
| `3.0` | 720p/480p | 5s/10s |
| `3.0-fast` | 720p/480p | 5s/10s |
| `s2.0` | 720p/480p | 5s |
| `2.0-pro` | 720p/480p | 5s |

---

## 前置条件

- Python 3.10+
- 即梦账号（[jimeng.jianying.com](https://jimeng.jianying.com) 注册，每日赠送免费积分）
- 从浏览器获取 Cookie 中的 `sessionid`

### 获取 sessionid

1. 在 Chrome 中打开 [https://jimeng.jianying.com](https://jimeng.jianying.com) 并登录
2. 按 `F12` → `Application` → `Cookies` → `jimeng.jianying.com`
3. 找到 `sessionid`，复制其 Value

```
sessionid  ← 类似: a1b2c3d4e5f6...
```

---

## 快速开始

```bash
# 1. 克隆
git clone git@github.com:NB4747/jimeng-free-tool-cli.git
cd jimeng-free-tool-cli

# 2. 安装依赖
pip install httpx pillow rembg

# 3. 设置 Cookie
# Windows
set JIMENG_COOKIE=你的sessionid

# macOS / Linux
export JIMENG_COOKIE=你的sessionid

# 4. 测试
python -c "
import asyncio, os
from src.jimeng_sdk import JimengClient

async def main():
    client = JimengClient(cookie=os.environ['JIMENG_COOKIE'], model='3.0', resolution='1k')
    credits = await client.get_credits()
    print(f'积分: {credits[\"total\"]}')

    task_id = await client.generate_image('a red circle on white background')
    url = await client.poll_task_status(task_id, timeout=120)
    print(f'图片: {url}')
    await client.close()

asyncio.run(main())
"
```

---

## Claude Code MCP 部署

### 一行命令免安装

```bash
claude mcp add jimeng -- uvx --from git+https://github.com/NB4747/jimeng-free-tool-cli.git jimeng-mcp
```

### 本地路径部署

```bash
claude mcp add jimeng -- py -3.12 "E:/your/path/jimeng-free-tool-cli/src/main.py"
```

### 环境变量配置

在 `.env` 或系统环境变量中设置：

```bash
JIMENG_COOKIE=你的sessionid
```

### 多账号 Token 轮询配置

如果有多个即梦账号，用逗号分隔多个 sessionid，SDK 自动 round-robin 轮询：

```bash
JIMENG_COOKIE=sid_account1
JIMENG_TOKENS=sid_account1,sid_account2,sid_account3
```

部署后重启 Claude Code，即可在对话中使用：

```
"画一只像素风的猫"
"把这个角色的背景去掉"
"生成一段5秒的爆炸特效视频"
"用这张草稿图生成同风格的变体"
```

---

## Python SDK 用法

### 文生图

```python
import asyncio, os
from src.jimeng_sdk import JimengClient

async def main():
    client = JimengClient(
        cookie=os.environ["JIMENG_COOKIE"],
        model="4.5",          # 模型: 4.5 / 4.1 / 4.0 / 3.1 / 3.0 / 2.0pro
        resolution="2k",      # 分辨率: 2k / 1k
    )
    task_id = await client.generate_image(
        "pixel art dragon, 16-bit, vibrant colors",
        aspect_ratio="16:9",  # 比例: 21:9/16:9/3:2/4:3/1:1/3:4/2:3/9:16
    )
    url = await client.poll_task_status(task_id, timeout=120)
    print(f"Image: {url}")
    await client.close()

asyncio.run(main())
```

### 图生图（用参考图生成变体）

```python
task_id = await client.generate_image_to_image(
    prompt="same style but wearing red armor",
    reference="path/to/original.png",  # 本地路径 / URL / CDN image_uri
    sample_strength=0.5,               # 参考强度 0-1
)
url = await client.poll_task_status(task_id)
```

### 文生视频

```python
task_id = await client.generate_video(
    "a magical portal opening in a classroom",
    ratio="16:9",
    resolution="720p",
    duration=5,           # 5 或 10 秒
)
# 视频生成比图片慢 (2-10 分钟)
url = await client.poll_video_status(task_id, timeout=600)
```

### 图生视频（用首尾帧生成过渡动画）

```python
task_id = await client.generate_video_with_frames(
    "smooth transition from day to night",
    first_frame="path/to/first.png",   # 可选
    end_frame="path/to/end.png",       # 可选
    duration=5,
)
url = await client.poll_video_status(task_id, timeout=600)
```

### 上传图片到即梦 CDN

```python
from src.jimeng_upload import upload_to_jimeng

image_uri = await upload_to_jimeng(
    "C:/art/character.png",
    cookie=os.environ["JIMENG_COOKIE"],
)
print(f"CDN URI: {image_uri}")
# 可以传给 generate_image_to_image() 或 generate_video_with_frames()
```

### 多账号轮询

```python
client = JimengClient(
    cookie="sid_main",                          # 主 token
    tokens="sid_acc1,sid_acc2,sid_acc3",        # 轮询列表
)
# 每次 API 调用自动切换到下一个 token
task_id = await client.generate_image("...")
# 这次用 acc1
task_id = await client.generate_image("...")
# 这次用 acc2，以此类推
```

---

## 游戏资产后处理

```python
from src.asset_processor import (
    remove_background,
    resize_to_game_standard,
    process_to_game_asset,
    GAME_STANDARDS,
)

# 读取图片
with open("raw.png", "rb") as f:
    raw = f.read()

# 去背 → RGBA 透明 PNG
transparent = remove_background(raw, alpha_matting=True)

# 缩放到游戏标准尺寸（保比例，居中填透明）
resized = resize_to_game_standard(transparent, (64, 64), pad_to_fit=True)

# 一步到位：去背 + 缩放
icon = process_to_game_asset(raw, preset="sprite")   # 256x256
icon = process_to_game_asset(raw, preset="icon")     # 64x64

# 支持的预设
print(GAME_STANDARDS)
# {'icon': (64,64), 'card': (128,128), 'sprite': (256,256),
#  'portrait': (512,512), 'bg': (1024,1024), 'full': (2048,2048)}
```

---

## 上传引擎

`jimeng_upload.py` 实现了完整的 ByteDance CDN 上传链路：

```
本地文件 → CRC32 校验 → 获取 STS Token → AWS V4 签名
→ imagex.bytedanceapi.com 申请上传 → 二进制上传
→ CommitImageUpload → 返回 image_uri
```

支持三种输入格式：

```python
await upload_to_jimeng("C:/art/hero.png", cookie)           # 本地文件
await upload_to_jimeng("https://example.com/img.jpg", cookie) # HTTP URL
await upload_to_jimeng("data:image/png;base64,...", cookie)   # Base64
```

---

## 配置参考

### config.json

```json
{
    "cdp_url": "http://localhost:9222",
    "default_output_dir": "./downloads",
    "task_timeout": 60,
    "api_patterns": ["api/v1/task", "aigc_dream", "mweb/v1"],
    "poll_interval": 1.0
}
```

### 环境变量

| 变量 | 必须 | 说明 |
|------|:--:|------|
| `JIMENG_COOKIE` | ✅ | 即梦 sessionid |
| `JIMENG_TOKENS` | 否 | 多账号轮询，逗号分隔 |
| `JIMENG_MODEL` | 否 | 默认模型，默认 `4.5` |
| `JIMENG_RESOLUTION` | 否 | 默认分辨率，默认 `2k` |

---

## 项目结构

```
jimeng-free-tool-cli/
├── README.md
├── pyproject.toml              # pip install -e .  或  uv sync
├── config.json                 # CDP + 超时 + API 模式
├── requirements.txt            # 传统 pip 依赖
└── src/
    ├── main.py                 # MCP 服务入口 (4 个工具)
    ├── jimeng_sdk.py           # 生产级 SDK (700+ 行)
    ├── jimeng_upload.py        # CDN 上传引擎 (300+ 行)
    ├── jimeng_api.py           # 底层 API 客户端
    ├── jimeng_client.py        # Playwright 浏览器自动化 (备用)
    ├── asset_processor.py      # rembg + Pillow 后处理
    └── utils.py                # 异步下载
```

---

## 常见问题

### Q: 提示"积分不足"？

A: 到 [jimeng.jianying.com](https://jimeng.jianying.com) 点击右上角积分图标领取每日免费积分。或使用 `model='3.0'` + `resolution='1k'` 经济模式。

### Q: Cookie 多久过期？

A: 通常 60 天。过期后重新从浏览器提取 sessionid。

### Q: 视频生成为什么很慢？

A: 视频生成需要 2-10 分钟，默认超时 20 分钟。这是即梦服务端处理时间，与 SDK 无关。

### Q: 如何查看当前积分？

```python
credits = await client.get_credits()
print(credits)  # {'gift': 94, 'purchase': 0, 'vip': 112, 'total': 206}
```

### Q: 可以不装 Playwright 吗？

A: 可以。如果只使用 API 模式（设置 `JIMENG_COOKIE`），完全不需要 Playwright。Playwright 只在浏览器自动化的备用模式中使用。

---

## License

MIT
