# 发布说明 / Release Notes

## v1.0.1

### 简体中文

此版本修复了一个会话数据保护问题：此前恢复“应用配置”前创建的快照时，工具会把快照中的旧会话文件和 SQLite 数据库覆盖到当前数据上，导致之后在 Responses API 模式下新增或更新的对话在 Codex 中消失。

#### 修复内容

- 默认恢复现在仅还原 Codex 配置和本工具生成的模型目录，不会覆盖当前本地对话、会话索引或 SQLite 会话数据库。
- 新增明确的“Full Data Recovery（完整数据恢复）”入口，仅在确实需要回退会话数据时使用。
- 每次恢复前自动创建安全快照；即使选择完整数据恢复，也可以回到恢复前的当前状态。
- 增加自动化回归测试，验证恢复旧配置后新的 Responses API 对话仍会保留。

#### 升级说明

直接下载并替换为本版本的 `CodexResponsesTool.exe`。普通恢复现在是安全的配置恢复；如需完整回退历史会话，请完全关闭 Codex 后使用“Full Data Recovery”。

#### 下载和校验

下载 `CodexResponsesTool.exe` 和同目录的 `CodexResponsesTool.exe.sha256`。运行前请核对 SHA-256：

`7b53ee7b27dc3da81e93334e6f06375617ff738b31a3cc153706ef82204fa2d7`

---

### English

This release fixes a conversation-data protection issue. Previously, restoring a snapshot created before applying configuration overwrote current session files and SQLite databases with the older snapshot. As a result, conversations created or updated later while using the Responses API could disappear from Codex.

#### Fixes

- Normal restore now restores only Codex configuration and this tool's model catalog. It does not overwrite current local conversations, session indexes, or SQLite session databases.
- Adds an explicit “Full Data Recovery” option for the rare case where conversation data truly needs to be rolled back.
- Automatically creates a safety snapshot before every restore, so full data recovery can be undone by restoring the pre-recovery state.
- Adds a regression test that verifies new Responses API conversations remain after restoring older configuration.

#### Upgrade notes

Download and replace your existing `CodexResponsesTool.exe` with this release. Normal restore is now safe for configuration recovery. To roll back historical conversation data, fully close Codex and use “Full Data Recovery”.

#### Download and verification

Download `CodexResponsesTool.exe` and `CodexResponsesTool.exe.sha256` from this release. Verify the SHA-256 checksum before running:

`7b53ee7b27dc3da81e93334e6f06375617ff738b31a3cc153706ef82204fa2d7`

## v1.0

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

---

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
