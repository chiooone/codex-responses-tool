# Codex Responses Tool

当前版本 / Current release：**v1.0.1**

[下载 v1.0.1 / Download v1.0.1](https://github.com/chiooone/codex-responses-tool/releases/tag/v1.0.1)

## 简体中文

Codex Responses Tool 是一个面向 Windows 的图形化工具，用于将 Codex 桌面应用连接到用户指定的 Responses API 地址。程序会在修改前自动备份本地 Codex 配置和对话数据。

### 功能

- 自动识别 `CODEX_HOME`；未设置时使用用户目录下的 `.codex`。
- 自动识别 `CODEX_SQLITE_HOME`；未设置时使用 `CODEX_HOME`。
- 检测 API 可用模型并通过列表供用户选择。
- 写入 Codex 的 `config.toml` 和 `cpa-gui-model-catalog.json`。
- provider 显示名称固定为 `Chione Codex`。
- 默认恢复仅还原 Codex 配置，保留当前本地对话数据；需要时可显式执行完整数据恢复。
- 切换 provider 时同步历史对话元数据，避免已有对话暂时消失。
- 将保存的 API 设置和快照存放在程序旁边的 `app_data` 目录中。

### 快速开始

1. 输入 Responses API 基础地址和 API Key。
2. 检测可用模型并选择默认模型。
3. 完全关闭 Codex，然后点击 `Apply to Codex`。
4. 出现成功提示后重新启动 Codex。
5. 如需恢复快照，请先完全关闭 Codex；普通恢复不会覆盖当前对话，完整数据恢复会先自动创建安全快照。

### 从源代码运行

可以运行 `start.bat`、在 PowerShell 中运行 `.\start.ps1`，或者执行：

```powershell
python app.py
```

### Windows 可执行文件

可以从 GitHub Releases 下载单文件版 `CodexResponsesTool.exe`，无需安装 Python。EXE 会把设置和快照保存在自身旁边的 `app_data` 目录中。

当前 EXE 尚未进行代码签名，因此 Windows SmartScreen 首次运行时可能显示警告。运行前请核对 Release 页面提供的 SHA-256 校验值。

### 构建可执行文件

```powershell
python -m pip install -r requirements-dev.txt
.\build_release.ps1
```

生成的可执行文件和 SHA-256 校验文件位于 `dist` 目录。

### 项目文件

- `app.py` — 主图形界面程序。
- `start.bat` — Windows 启动脚本。
- `start.ps1` — PowerShell 启动脚本。
- `build_release.ps1` — 可重复执行的 Windows Release 构建脚本。
- `assets/codex_model_catalog.json` — 内置 Codex 模型目录模板。

### 说明

- 本工具只进行本地文件备份和恢复操作。
- 通过环境变量修改 Codex 数据位置后，程序会自动识别新路径。
- 本工具创建的快照保存在 `app_data/backups` 中。
- 应用 provider 时会更新兼容的 rollout `session_meta` 记录和 SQLite `threads` 数据；操作前会先创建快照，因此可以恢复。

## English

Codex Responses Tool is a Windows-first graphical utility that connects Codex Desktop to a user-provided Responses API endpoint. Before making changes, it automatically backs up the local Codex configuration and conversation data.

### Features

- Detects `CODEX_HOME`, falling back to the user `.codex` directory when unset.
- Detects `CODEX_SQLITE_HOME`, falling back to `CODEX_HOME` when unset.
- Detects available API models and presents them in a selection list.
- Writes Codex `config.toml` and `cpa-gui-model-catalog.json`.
- Uses the fixed provider display name `Chione Codex`.
- Normal restore changes only Codex configuration and preserves current local conversations; full data recovery is explicit.
- Synchronizes historical conversation metadata when switching providers so existing conversations remain visible.
- Stores saved API settings and snapshots in `app_data` next to the program.

### Quick start

1. Enter the Responses API base URL and API key.
2. Detect the available models and select a default model.
3. Close Codex, then click `Apply to Codex`.
4. Restart Codex after the success message appears.
5. To restore a snapshot, completely close Codex. Normal restore does not overwrite current conversations, while full data recovery first creates a safety snapshot.

### Run from source

Use `start.bat`, run `.\start.ps1` in PowerShell, or run:

```powershell
python app.py
```

### Windows executable

Download the single-file `CodexResponsesTool.exe` from GitHub Releases. Python is not required. The executable stores settings and snapshots under `app_data` next to the executable.

The executable is currently unsigned, so Windows SmartScreen may display a warning the first time it runs. Verify the SHA-256 checksum shown on the Release page before running it.

### Build the executable

```powershell
python -m pip install -r requirements-dev.txt
.\build_release.ps1
```

The executable and SHA-256 checksum are written to `dist`.

### Project files

- `app.py` — main GUI application.
- `start.bat` — Windows launcher.
- `start.ps1` — PowerShell launcher.
- `build_release.ps1` — reproducible Windows release build script.
- `assets/codex_model_catalog.json` — bundled Codex model catalog template.

### Notes

- The tool only performs local file backup and restore operations.
- Environment-variable changes to Codex storage locations are detected automatically.
- Snapshots created by this tool are stored under `app_data/backups`.
- Applying a provider updates compatible rollout `session_meta` records and SQLite `threads` rows. A snapshot is created first so the operation remains reversible.
