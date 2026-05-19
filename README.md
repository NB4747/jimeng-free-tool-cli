# jimeng-mcp-bridge

基于 Playwright CDP 的即梦（jimeng.jianying.com）文本生图 MCP 服务。允许 AI 代理（如 Claude Code）接管本地已登录的 Chrome 浏览器，全自动操作即梦网页端生图，并通过拦截网络请求获取高清图片 URL 并下载到本地。


## 前置条件

- Python 3.10+
- Chrome / Chromium 浏览器（你用 CDP 启动的那个）


## 快速开始

### 1. 安装依赖

```bash
cd jimeng-mcp-bridge
py -3.12 -m pip install -r requirements.txt
```

> 本项目通过 CDP 连接你本机的 Chrome，无需安装 Playwright 自带的 Chromium。

### 2. 启动宿主浏览器（带 CDP 端口）

**重要：** 在启动本服务前，必须完全关闭所有 Chrome 窗口，然后用以下命令重新启动：

**Windows:**
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeProfileForAgent"
```

**macOS:**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeProfileForAgent"
```

**Linux:**
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/ChromeProfileForAgent"
```

启动后，在弹出的 Chrome 窗口中手动打开 [https://jimeng.jianying.com/ai-tool/home/](https://jimeng.jianying.com/ai-tool/home/) 并完成登录（扫码或手机验证码）。

### 3. 验证 CDP 连接

浏览器启动后，访问 [http://localhost:9222/json](http://localhost:9222/json) 应能看到页面列表 JSON。

### 4. 在 Claude Code 中配置 MCP

在 Claude Code 的 MCP 配置文件中添加（项目级 `.claudecode/mcp_config.json` 或全局 `~/.config/Claude/claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "jimeng-bridge": {
      "command": "py",
      "args": ["-3.12", "E:/即梦skill/jimeng-mcp-bridge/src/main.py"]
    }
  }
}
```

> 将路径替换为你本机的实际绝对路径。

### 5. 使用

配置完成后重启 Claude Code，即可调用 `generate_game_asset` 工具：

```
请用 generate_game_asset 生成一张图片，提示词：一只在森林里奔跑的白色狐狸，油画风格
```


## 项目结构

```
jimeng-mcp-bridge/
├── requirements.txt      # Python 依赖
├── config.json           # 配置文件（CDP 端口、超时、下载路径）
├── README.md
└── src/
    ├── __init__.py
    ├── main.py           # FastMCP 服务入口与工具定义
    ├── jimeng_client.py  # Playwright CDP 核心控制与网络拦截
    └── utils.py          # 异步图片下载工具
```


## config.json 说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cdp_url` | string | `"http://localhost:9222"` | Chrome CDP 地址 |
| `default_output_dir` | string | `"./downloads"` | 默认图片保存目录 |
| `task_timeout` | number | `60` | 生图任务超时（秒） |
| `api_patterns` | array | `["api/v1/task", ...]` | 拦截 API 的 URL 正则模式 |
| `poll_interval` | number | `1.0` | 轮询间隔（秒） |


## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| "无法连接到 Chrome" | Chrome 未以 CDP 模式启动，或端口被占用 | 完全关闭 Chrome，按步骤 2 重新启动 |
| "登录状态已失效" | 即梦网站登录过期 | 在弹出 Chrome 中手动重新登录即梦 |
| 超时未获取到图片 | API URL 特征变化 | 检查实际网络请求，更新 config.json 中的 `api_patterns` |
| "Cannot locate the prompt input box" | 即梦页面 UI 改版 | 更新 `jimeng_client.py` 中的 `_INPUT_PLACEHOLDERS` 选择器 |


## 技术原理

1. 通过 Playwright 的 `connect_over_cdp` 接入用户本地 Chrome
2. 复用已登录的 jimeng.jianying.com 页面，无需程序内填账号密码
3. 在 `page.on("response")` 上注册监听器，拦截即梦后端 API 响应
4. 从 JSON 响应体中提取高清图片 URL（多路径兼容）
5. 使用 httpx 流式下载大图到本地磁盘
