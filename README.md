# jimeng-free-tool-cli

> 即梦 AI 免费工具 CLI — 文生图 / 图生图 / 视频生成 / 资产管理一体化命令行工具

无需 API Key，无需付费接口。通过即梦 Cookie 调用官方 REST API，支持 6 款图像模型、5 款视频模型，2K 高清输出，带完整的游戏资产后处理管线。

---

## 目录

- [功能矩阵](#功能矩阵)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [Claude Code MCP 部署](#claude-code-mcp-部署)
- [Claude Code 对话使用指南](#claude-code-对话使用指南)
- [Claude Code × CCGS Agent 集成](#claude-code--ccgs-agent-集成)
- [Python SDK 用法](#python-sdk-用法)
- [游戏资产后处理](#游戏资产后处理)
- [上传引擎](#上传引擎)
- [MCP 工具参数参考](#mcp-工具参数参考)
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

---

## Claude Code MCP 部署

### 方式一：一行命令远程安装（推荐）

```bash
claude mcp add jimeng -- uvx --from git+https://github.com/NB4747/jimeng-free-tool-cli.git jimeng-mcp
```

> 把 `NB4747` 替换为你的 GitHub 用户名（如果你 fork 了仓库）。

### 方式二：本地路径安装

```bash
claude mcp add jimeng -- py -3.12 "E:/your/path/jimeng-free-tool-cli/src/main.py"
```

### 方式三：配合 uv 项目安装

```bash
cd jimeng-free-tool-cli
uv sync
claude mcp add jimeng -- uv run jimeng-mcp
```

### 环境变量配置

在项目根目录创建 `.env` 文件（已在 `.gitignore` 中排除）：

```bash
JIMENG_COOKIE=你的sessionid
```

### 多账号轮询

```bash
JIMENG_COOKIE=sid_main
JIMENG_TOKENS=sid_acc1,sid_acc2,sid_acc3
```

### 验证部署

```bash
# 检查 MCP 服务是否注册成功
claude mcp list

# 查看 jimeng 服务详情
claude mcp get jimeng
```

预期输出：
```
jimeng:
  Status: ✓ Connected
  Type: stdio
  Command: py -3.12 .../src/main.py
```

---

## Claude Code 对话使用指南

> **重点**：部署完成后**重启 Claude Code**，工具即生效。以下所有对话示例均可直接使用，工具自动识别意图。

### 场景一：直接文生图

你不需要说"调用 generate_game_asset"，直接用大白话即可：

```
"画一只像素风的猫，16-bit 风格，橘色虎斑，白色背景"
```

Claude 的实际执行流程：
```
1. 识别意图 "画一只..." → 匹配 trigger words
2. 自动翻译为英文 prompt: "pixel art orange tabby cat, 16-bit style, white background"
3. 调用 generate_game_asset(prompt="...")
4. 等待即梦 API 返回图片 URL
5. 下载图片到 ./downloads/
6. 回复你: "图片已保存至 ./downloads/xxx.png"
```

### 场景二：指定技术参数

```
"生成一张游戏角色 Sprite，中性灰色调，48x48 像素，8 方向，用于 Godot AtlasTexture"

"做一个 16:9 横屏的赛博朋克城市夜景，2K 分辨率"

"画一个技能图标，24x24，要透明背景，放到 assets/ui/skill_icon.png"
```

Claude 会自动把尺寸、比例、路径等约束注入到工具参数中。

### 场景三：游戏工作流对话（多轮交互）

```
你: "扫描一下我的游戏项目，看看缺哪些美术资源"

Claude: [调用 AssetAuditorAgent 扫描代码]
        "发现 3 个缺失资产：
         1. assets/characters/hero.png (64x64 sprite) — 缺失
         2. assets/tiles/grass.png (16x16 tile) — 缺失  
         3. assets/ui/health_bar.png (256x16) — 缺失"

你: "把这三个全生成出来"

Claude: [依次调用 generate_game_asset × 3]
        "全部生成完毕：
         ✅ hero.png (64x64, RGBA)
         ✅ grass.png (16x16, TileSet ready)
         ✅ health_bar.png (256x16, NinePatchRect ready)"
```

### 场景四：资产迭代与微调

```
你: "这个角色的背景没去干净，帮我处理一下"

Claude: [读取图片 → 调用 asset_processor.remove_background()]
        "已处理，去背后保存为 hero_no_bg.png"
```

```
你: "用这张 boss.png 做参考，生成一个红色盔甲版本的变体"

Claude: [上传 boss.png → 调用 generate_image_variation()]
        "变体已生成 → boss_red_armor.png"
```

### 场景五：视频生成

> ⚠️ 视频消耗积分较多，建议确认需求后再执行。

```
你: "生成一段 5 秒的魔法传送门特效视频，16:9，适合做过场动画"

Claude: [调用 generate_video_asset]
        "视频任务已提交 (task_id=xxx)，预计 2-5 分钟..."
        "视频已保存至 ./downloads/portal_cutscene.mp4"
```

```
你: "用这张教室照片做首帧，这张走廊照片做尾帧，生成过渡视频"

Claude: [上传两张图 → 调用 generate_video_with_frames]
        "图生视频完成 → classroom_to_hallway.mp4"
```

### 场景六：批量资产生产

```
你: "我需要一套完整的 RPG 道具包：
     1. 红色血瓶 (16x16)
     2. 蓝色魔法瓶 (16x16)
     3. 铁剑 (32x32)
     4. 木盾 (32x32)
     5. 金色钥匙 (16x16)
     全部去背，放到 assets/items/ 下面"

Claude: [自动循环 5 次]
        "5 个道具全部生成并去背完毕：
         ✅ assets/items/health_potion.png
         ✅ assets/items/mana_potion.png
         ✅ assets/items/iron_sword.png
         ✅ assets/items/wooden_shield.png
         ✅ assets/items/golden_key.png"
```

### 自动意图识别关键字

以下任意说法都能触发 MCP 工具自动调用：

| 类别 | 触发词 |
|------|--------|
| 文生图 | 画 / 生成图片 / 做图 / 创作 / 设计 / sprite / asset / icon / background / texture / pixel art |
| 图生图 | 参考这张图 / 基于这张 / 变体 / 换个颜色 / 改风格 / variation |
| 视频 | 生成视频 / 做动画 / 过场 / cutscene / 特效视频 / 动态背景 |
| 去背 | 去背景 / 扣图 / 透明 / remove background / alpha channel |
| 缩放 | 缩放 / resize / 改成 xx像素 / 64x64 |

### 积分管理对话

```
你: "我还有多少积分？"

Claude: [调用 get_credits()]
        "当前积分: 206 (VIP 112 + 赠送 94)"
```

### 输出路径规则

Claude 会根据上下文自动推断保存路径：

| 你说 | 保存到 |
|------|--------|
| "画一只猫" | `./downloads/画一只猫.png` |
| "存到 assets/player.png" | `assets/player.png` |
| "生成角色，放到 characters/hero" | `characters/hero.png` |
| 不指定路径 | `./downloads/<prompt前80字>.png` |

### 错误处理对话

```
你: "画一只猫"

Claude: "【错误】即梦积分不足，请前往 https://jimeng.jianying.com 领取每日积分。"
        "当前积分: 0。是否需要我切换到经济模式重试？"

你: "用经济模式"

Claude: [切换 model='3.0', resolution='1k']
        "已切换。经济模式每次约消耗 1 积分。正在重试..."
```

---

## Claude Code × CCGS Agent 集成

如果你同时安装了 [Claude-Code-Game-Studios](https://github.com/NB4747/jimeng-tools) 框架，可以获得更专业的 Agent 协作体验：

```
# 注册即梦工具
claude mcp add jimeng -- py -3.12 ".../src/main.py"

# CCGS 的 Agent 会自动发现 jimeng 工具并协作
/asset-spec          # Art Director: 扫描缺口 + 扩写 prompt + 批量规划
/map-systems 教室    # Level Designer: 规划 TileSet 物理层
/consistency-check   # VFX Artist: 校验动画帧率 + Spritesheet 网格
/smoke-check         # QA Lead: 验证生成资产尺寸/透明/路径
```

详细的 CCGS Agent 使用指南见 [.claude/tasks/generate_art_pipeline.md](https://github.com/NB4747/jimeng-tools/blob/main/.claude/tasks/generate_art_pipeline.md)。

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

---

## MCP 工具参数参考

> 以下为 4 个注册工具的完整参数表。Claude 调用时自动填参。

### `generate_game_asset` — 文生图

| 参数 | 类型 | 必须 | 默认值 | 说明 |
|------|------|:--:|--------|------|
| `prompt` | string | ✅ | — | 自然语言画面描述（中英文均可） |
| `output_path` | string | 否 | `./downloads/<prompt>.png` | 保存路径 |

### `generate_image_variation` — 图生图

| 参数 | 类型 | 必须 | 默认值 | 说明 |
|------|------|:--:|--------|------|
| `prompt` | string | ✅ | — | 目标画面描述 |
| `reference_path` | string | ✅ | — | 参考图路径（本地文件/URL/Base64） |
| `output_path` | string | 否 | `./downloads/<prompt>.png` | 保存路径 |

### `generate_video_asset` — 文生视频

| 参数 | 类型 | 必须 | 默认值 | 说明 |
|------|------|:--:|--------|------|
| `prompt` | string | ✅ | — | 视频描述 |
| `duration` | int | 否 | `5` | 时长：5 或 10 秒 |
| `ratio` | string | 否 | `"16:9"` | 比例：16:9/9:16/1:1/4:3/3:4/21:9 |
| `resolution` | string | 否 | `"720p"` | 分辨率：1080p/720p/480p |
| `output_path` | string | 否 | `./downloads/<prompt>.mp4` | 保存路径 |

### `generate_video_with_frames` — 图生视频

| 参数 | 类型 | 必须 | 默认值 | 说明 |
|------|------|:--:|--------|------|
| `prompt` | string | ✅ | — | 视频描述 |
| `first_frame` | string | 否 | `""` | 首帧图路径（本地/URL） |
| `end_frame` | string | 否 | `""` | 尾帧图路径（本地/URL） |
| `duration` | int | 否 | `5` | 时长：5 或 10 秒 |
| `ratio` | string | 否 | `"16:9"` | 比例 |
| `output_path` | string | 否 | `./downloads/<prompt>.mp4` | 保存路径 |

---

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
