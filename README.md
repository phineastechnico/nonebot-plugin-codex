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
# Codex 可执行文件名或绝对路径，默认直接调用 PATH 里的 `codex`
codex_binary = "codex"

# 默认工作目录；新会话、目录浏览器 Home 入口、相对路径解析都会基于它
codex_workdir = "/home/yourname"

# `/stop` 或重置会话时，等待 Codex 子进程退出的超时时间（秒）
codex_kill_timeout = 5.0

# 运行中在 Telegram 里保留多少条“进度日志”
codex_progress_history = 6

# 运行失败时最多保留多少条诊断输出，便于排查问题
codex_diagnostic_history = 20

# 单条 Telegram 消息的分片长度；回复太长时会自动拆分
codex_chunk_size = 3500

# 读取 Codex stdout/stderr 的缓冲区大小
codex_stream_read_limit = 1048576

# Codex 本地模型缓存文件；`/models`、`/model` 会读取这里
codex_models_cache_path = "/home/yourname/.codex/models_cache.json"

# Codex CLI 的配置文件；会从这里读取默认模型和推理强度
codex_codex_config_path = "/home/yourname/.codex/config.toml"

# 插件保存“每个聊天偏好设置”的文件，例如模型、权限、工作目录、默认模式
codex_preferences_path = "data/codex_bridge/preferences.json"

# Codex 历史会话索引；`/sessions` 会先读它来列出 exec 历史
codex_session_index_path = "/home/yourname/.codex/session_index.jsonl"

# Codex 当前会话日志目录；用于补充历史会话的标题、预览和 cwd 信息
codex_sessions_dir = "/home/yourname/.codex/sessions"

# Codex 归档会话目录；历史浏览也会读取这里
codex_archived_sessions_dir = "/home/yourname/.codex/archived_sessions"
```

- `codex_binary`：如果你的机器上不是直接执行 `codex`，这里改成绝对路径。
- `codex_workdir`：最重要的配置之一。它决定插件默认在哪个目录里运行 Codex，也影响 `/cd` 相对路径的解析基准。
- `codex_preferences_path`：这是插件自己的状态文件，不是 Codex 官方文件。删掉它会丢失每个聊天保存的模型、权限、工作目录和默认模式。
- `codex_models_cache_path`、`codex_codex_config_path`：这是读取 Codex 本机配置和模型信息用的，通常保持默认即可。
- `codex_session_index_path`、`codex_sessions_dir`、`codex_archived_sessions_dir`：这是历史会话浏览功能依赖的路径；如果你改了 Codex 的数据目录，这三项要一起对应修改。

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
