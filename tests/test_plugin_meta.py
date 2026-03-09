from __future__ import annotations

from nonebot_plugin_codex import __plugin_meta__


def test_plugin_metadata_uses_string_adapter_names() -> None:
    assert __plugin_meta__.homepage == "https://github.com/ttiee/nonebot-plugin-codex"
    assert __plugin_meta__.supported_adapters == {"~telegram"}
