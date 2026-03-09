<div align="center">

# nonebot-plugin-codex

_✨ 在 Telegram 里驱动 Codex CLI 的 NoneBot 插件 ✨_

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/ttiee/nonebot-plugin-codex.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-codex">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-codex.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

</div>

## 介绍

`nonebot-plugin-codex` 把本机 `codex` CLI 包装成 Telegram 里的对话式插件。

它保留了原 `codex_bridge` 的主要能力：

- Telegram 命令面板和普通消息续聊
- `resume/native` 与 `exec` 双模式
- 每个聊天独立的会话、模型、推理强度、权限、工作目录
- 目录浏览器与历史会话浏览器
- 兼容现有 `data/codex_bridge/preferences.json` 偏好文件和 `~/.codex/*` 历史数据

## 安装

### 使用 nb-cli

在 NoneBot 项目根目录执行：

```bash
nb plugin install nonebot-plugin-codex
```

### 使用包管理器

```bash
pip install nonebot-plugin-codex
```

或：

```bash
pdm add nonebot-plugin-codex
```

然后在 `pyproject.toml` 的 `[tool.nonebot]` 中启用：

```toml
plugins = ["nonebot_plugin_codex"]
```

## 前置条件

- Python 3.10+
- NoneBot 2.4.4+
- `nonebot-adapter-telegram`
- 本机已安装并可直接执行 `codex`

## 配置

推荐使用以下正式配置名：

```toml
[tool.nonebot]
plugins = ["nonebot_plugin_codex"]

[tool.nonebot.plugin_config]
codex_binary = "codex"
codex_workdir = "/home/yourname"
codex_kill_timeout = 5.0
codex_progress_history = 6
codex_diagnostic_history = 20
codex_chunk_size = 3500
codex_stream_read_limit = 1048576
codex_models_cache_path = "/home/yourname/.codex/models_cache.json"
codex_codex_config_path = "/home/yourname/.codex/config.toml"
codex_preferences_path = "data/codex_bridge/preferences.json"
codex_session_index_path = "/home/yourname/.codex/session_index.jsonl"
codex_sessions_dir = "/home/yourname/.codex/sessions"
codex_archived_sessions_dir = "/home/yourname/.codex/archived_sessions"
```

兼容旧配置名：现有 `codex_bridge_*` 配置项仍然可用。

## 命令

- `/codex [prompt]` 连接 Codex；带 prompt 时直接发送
- `/mode [resume|exec]` 查看或切换默认模式
- `/exec <prompt>` 用一次性 `exec` 模式执行
- `/new` 清空当前聊天绑定的会话
- `/stop` 断开当前聊天的 Codex 会话
- `/models` 查看可用模型
- `/model [slug]` 查看或切换模型
- `/effort [high|xhigh]` 查看或切换推理强度
- `/permission [safe|danger]` 查看或切换权限模式
- `/pwd` 查看当前工作目录和当前设置
- `/cd [path]` 直接切目录；不带参数时打开目录浏览器
- `/home` 将工作目录重置到 Home
- `/sessions` 打开历史会话浏览器

在 `/codex` 连接后，普通文本消息会自动续聊当前会话。

## 模式说明

### `resume`

- 优先使用 `codex app-server`
- 为同一聊天维持 native thread
- 更适合持续对话

### `exec`

- 使用 `codex exec --json`
- 支持恢复已有 exec thread
- 恢复失败时会自动新开会话并提示

## 目录与历史浏览

- `/cd` 会打开目录浏览器，可逐级进入、切换 Home、显示隐藏目录，并将当前浏览目录设为工作目录
- `/sessions` 会列出 native 与 exec 历史会话
- 历史会话恢复时会尝试切回原始工作目录；目录不存在时会保留当前目录并提示

## 兼容说明

- 默认偏好文件仍然是 `data/codex_bridge/preferences.json`
- 历史会话仍然读取 `~/.codex/session_index.jsonl`、`~/.codex/sessions`、`~/.codex/archived_sessions`
- 这意味着可以从现有 `~/tg_bot/plugins/codex_bridge` 平滑迁入，不需要额外迁移脚本

## 发布

仓库自带 GitHub Actions：

- `test.yml` 负责安装依赖并运行测试
- `release.yml` 在打 `v*` tag 时执行 `pdm publish` 并上传构建产物

发布前请先在 PyPI 的 Trusted Publishing 中添加：

- Project name: `nonebot-plugin-codex`
- Owner: `ttiee`
- Repository name: `nonebot-plugin-codex`
- Workflow name: `release.yml`

## 开发

```bash
pdm sync -G:all
pdm run pytest
pdm run ruff check .
pdm build
```
