# Release Notes / 发布说明

## v1.0

### English

Codex Responses Tool v1.0 is the first Windows release. It provides a graphical way to connect Codex Desktop to a custom Responses API endpoint while protecting local configuration and conversation data with automatic snapshots.

#### Highlights

- Configure a custom Responses API base URL and API key.
- Detect available models and select the default model from a list.
- Write the required Codex provider and model catalog configuration.
- Back up Codex configuration, authentication-related files, session data, and compatible SQLite databases before changes.
- Synchronize historical conversation provider metadata so existing conversations remain visible after switching providers.
- Restore previous snapshots after Codex has been completely closed.
- Store saved settings and backups in `app_data` next to the executable.

#### Download and use

1. Download `CodexResponsesTool.exe` below. Python is not required.
2. Verify the SHA-256 checksum before running the file.
3. Enter the API address and key, detect models, and select a model.
4. Completely close Codex before applying configuration or restoring a snapshot.
5. Restart Codex after the operation succeeds.

#### Important notice

The executable is currently unsigned. Windows SmartScreen may display a warning the first time it runs. Select **More info** and verify the file source and checksum before choosing **Run anyway**.

**SHA-256:** `5373a261457373b3cff6e027ce2d2577c9ba2aa64228d58ab7902389fa2b36de`

---

### 简体中文

Codex Responses Tool v1.0 是首个 Windows 正式版本。它通过图形界面将 Codex 桌面应用连接到自定义 Responses API，并使用自动快照保护本地配置和对话数据。

#### 主要功能

- 配置自定义 Responses API 基础地址和 API Key。
- 检测可用模型，并从列表中选择默认模型。
- 写入 Codex 所需的 provider 和模型目录配置。
- 修改前备份 Codex 配置、身份验证相关文件、会话数据和兼容的 SQLite 数据库。
- 同步历史对话的 provider 元数据，避免切换 provider 后已有对话暂时消失。
- 完全关闭 Codex 后恢复之前创建的快照。
- 将保存的设置和备份存放在 EXE 旁边的 `app_data` 目录中。

#### 下载和使用

1. 下载下方的 `CodexResponsesTool.exe`，无需安装 Python。
2. 运行前核对 SHA-256 校验值。
3. 输入 API 地址和 Key，检测模型并选择需要使用的模型。
4. 应用配置或恢复快照前，请完全关闭 Codex。
5. 操作成功后重新启动 Codex。

#### 重要提示

当前 EXE 尚未进行代码签名，因此 Windows SmartScreen 首次运行时可能显示警告。请选择**更多信息**，确认文件来源和校验值后再选择**仍要运行**。

**SHA-256：** `5373a261457373b3cff6e027ce2d2577c9ba2aa64228d58ab7902389fa2b36de`
