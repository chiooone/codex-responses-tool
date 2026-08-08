# Codex Responses Tool

中文

这是一个面向 Windows 的图形化小工具，用来把 Codex 切换到你指定的 Responses API 地址，并在修改前自动备份本地配置与会话数据。

它会处理这些内容：

- 识别 `CODEX_HOME`，没有设置时默认使用用户目录下的 `.codex`
- 识别 `CODEX_SQLITE_HOME`，没有设置时回落到 `CODEX_HOME`
- 写入 Codex 的 `config.toml`
- 写入 Codex 的 `cpa-gui-model-catalog.json`
- 备份与恢复原始配置
- 备份与恢复本地会话相关文件
- 切换 provider 时同步历史会话元数据，避免旧对话在 Codex 中暂时消失
- 将工具自己的备份保存在项目目录内


English

This is a Windows-first GUI utility for switching Codex to a user-provided Responses API endpoint while automatically backing up local configuration and session data before changes.

It handles:

- Detecting `CODEX_HOME`, falling back to the user `.codex` folder when unset
- Detecting `CODEX_SQLITE_HOME`, falling back to `CODEX_HOME` when unset
- Writing Codex `config.toml`
- Writing Codex `cpa-gui-model-catalog.json`
- Backing up and restoring the original configuration
- Backing up and restoring local session-related files
- Synchronizing historical session metadata when the provider changes so existing conversations remain visible
- Storing the tool's own backups inside the project directory


## Quick Start / 快速开始

1. Fill in the Responses API base URL, API key, and default model.
2. Close Codex, then click `Apply to Codex`.
3. Restart Codex after the success message appears.
4. To restore a snapshot, close Codex first and then confirm the restore warning.

## Launch / 启动

Windows batch file:

```bat
start.bat
```

PowerShell:

```powershell
.\start.ps1
```

Or run directly:

```bash
python app.py
```

## Files / 文件

- `app.py` - main GUI application
- `start.bat` - Windows launcher
- `start.ps1` - PowerShell launcher
- `assets/codex_model_catalog.json` - bundled Codex catalog template

## Notes / 说明

- The tool uses local file backup and restore only.
- If you move Codex to a different home via environment variables, the app will resolve the new location automatically.
- Restore works from snapshots created by this tool.
- Backups created by this tool stay under the project folder in `app_data/backups`.
- Applying a provider also updates `session_meta` and compatible SQLite `threads` rows to the active provider. A snapshot is created first, so this operation remains reversible.
