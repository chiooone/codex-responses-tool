from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk


APP_NAME = "Codex Responses Tool"
APP_VERSION = "1.0"
PROGRAM_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
APP_DIR = PROGRAM_DIR / "app_data"
BACKUP_DIR = APP_DIR / "backups"
SETTINGS_FILE = "settings.json"
TEMPLATE_CATALOG_PATH = Path(__file__).with_name("assets") / "codex_model_catalog.json"
MANAGED_PROVIDER_ID = "cpa-gui"
DEFAULT_PROVIDER_NAME = "Chione Codex"
MANAGED_CATALOG_FILE = "cpa-gui-model-catalog.json"
MANAGED_ROOT_KEYS = {
    "model_provider",
    "model",
    "model_catalog_json",
}


@dataclass
class RuntimeModel:
    slug: str
    display_name: str | None = None
    description: str | None = None
    context_window: int | None = None
    max_context_window: int | None = None
    input_modalities: list[str] | None = None
    supported_reasoning_levels: list[str] | None = None
    default_reasoning_level: str | None = None
    hidden: bool = False


def ensure_directories() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def settings_path() -> Path:
    return APP_DIR / SETTINGS_FILE


def load_settings() -> dict[str, str]:
    path = settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, str] = {}
    for key in ("base_url", "api_key", "model"):
        value = data.get(key)
        if isinstance(value, str):
            result[key] = value
    return result


def save_settings(values: dict[str, str]) -> None:
    ensure_directories()
    payload = {key: values.get(key, "") for key in ("base_url", "api_key", "model")}
    write_text(settings_path(), json.dumps(payload, ensure_ascii=False, indent=2))


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


def resolve_codex_home() -> Path:
    value = os.environ.get("CODEX_HOME")
    if value:
        return expand_path(value)
    return Path.home() / ".codex"


def resolve_codex_sqlite_home(codex_home: Path) -> Path:
    value = os.environ.get("CODEX_SQLITE_HOME")
    if value:
        return expand_path(value)
    return codex_home


def normalize_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("Responses API base URL cannot be empty.")
    return value if value.endswith("/v1") else f"{value}/v1"


def read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def copy_item(src: Path, dst: Path) -> list[str]:
    changed: list[str] = []
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        changed.append(str(dst))
        return changed
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        changed.append(str(dst))
    return changed


def list_legacysqlite_sidecars(path: Path) -> list[Path]:
    if not path.is_file():
        return []
    result = [path]
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{path}{suffix}")
        if sidecar.is_file():
            result.append(sidecar)
    return result


def snapshot_items_for_root(root: Path) -> list[tuple[Path, Path]]:
    items: list[tuple[Path, Path]] = []
    if not root.exists():
        return items
    for rel in [
        "config.toml",
        "auth.json",
        MANAGED_CATALOG_FILE,
        "session_index.jsonl",
        ".codex-global-state.json",
        "logs_2.sqlite",
        "sessions",
        "archived_sessions",
        "sqlite",
        "state_5.sqlite",
    ]:
        src = root / rel
        if not src.exists():
            continue
        if src.is_file() and src.suffix == ".sqlite":
            for sidecar in list_legacysqlite_sidecars(src):
                items.append((sidecar, Path(sidecar.name)))
        else:
            items.append((src, Path(rel)))
    return items


def create_snapshot(codex_home: Path, sqlite_home: Path, reason: str) -> Path:
    ensure_directories()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_dir = BACKUP_DIR / f"{timestamp}-{int(time.time() * 1000) % 100000}"
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    metadata: dict[str, Any] = {
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
        "codexHome": str(codex_home),
        "codexSqliteHome": str(sqlite_home),
        "roots": [],
    }

    roots: list[tuple[str, Path]] = [("codex_home", codex_home)]
    if sqlite_home != codex_home:
        roots.append(("codex_sqlite_home", sqlite_home))

    for kind, root_path in roots:
        copied: list[str] = []
        for src, relative in snapshot_items_for_root(root_path):
            target = snapshot_dir / "payload" / kind / relative
            if src.is_dir():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
            copied.append(str(relative))
        metadata["roots"].append({
            "kind": kind,
            "sourceRoot": str(root_path),
            "items": copied,
        })

    write_text(snapshot_dir / "snapshot.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    return snapshot_dir


def load_snapshot_metadata(snapshot_dir: Path) -> dict[str, Any]:
    return json.loads((snapshot_dir / "snapshot.json").read_text(encoding="utf-8"))


def restore_snapshot(snapshot_dir: Path, codex_home: Path, sqlite_home: Path) -> list[str]:
    payload = snapshot_dir / "payload"
    if not payload.is_dir():
        raise FileNotFoundError("Snapshot payload folder not found.")
    restored: list[str] = []
    for kind, target_root in [("codex_home", codex_home), ("codex_sqlite_home", sqlite_home)]:
        root_payload = payload / kind
        if not root_payload.exists():
            continue
        for item in root_payload.rglob("*"):
            if item.is_dir():
                continue
            relative = item.relative_to(root_payload)
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            restored.append(str(target))
    return restored


def discover_session_databases(sqlite_home: Path) -> list[Path]:
    candidates: list[Path] = []
    sqlite_dir = sqlite_home / "sqlite"
    if sqlite_dir.is_dir():
        for path in sqlite_dir.iterdir():
            if path.is_file() and path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                candidates.append(path)
    legacy = sqlite_home / "state_5.sqlite"
    if legacy.is_file() and legacy not in candidates:
        candidates.append(legacy)
    return sorted(candidates, key=lambda path: str(path).lower())


def collect_rollout_files(codex_home: Path) -> list[Path]:
    files: list[Path] = []
    for directory in ("sessions", "archived_sessions"):
        root = codex_home / directory
        if root.is_dir():
            files.extend(path for path in root.rglob("*.jsonl") if path.is_file())
    return sorted(files, key=lambda path: str(path).lower())


def _rewrite_rollout_provider(path: Path, target_provider: str) -> tuple[bytes, bytes, str | None, str | None, bool] | None:
    original = path.read_bytes()
    text = original.decode("utf-8")
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    changed = False
    found_session_meta = False
    thread_id: str | None = None
    cwd: str | None = None
    has_user_event = '"user_message"' in text or '"user_input"' in text

    for line in lines:
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        rendered = body
        try:
            record = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            record = None
        if isinstance(record, dict) and record.get("type") == "session_meta":
            payload = record.get("payload")
            if isinstance(payload, dict):
                found_session_meta = True
                if thread_id is None and isinstance(payload.get("id"), str):
                    thread_id = payload["id"].strip() or None
                if cwd is None and isinstance(payload.get("cwd"), str):
                    cwd = payload["cwd"].strip() or None
                if payload.get("model_provider") != target_provider:
                    payload["model_provider"] = target_provider
                    rendered = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    changed = True
        output.append(rendered + ending)

    if not found_session_meta:
        return None
    return original, "".join(output).encode("utf-8"), thread_id, cwd, has_user_event


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.chione-tmp-{os.getpid()}-{threading.get_ident()}")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def repair_session_provider_metadata(
    codex_home: Path,
    sqlite_home: Path,
    target_provider: str = MANAGED_PROVIDER_ID,
) -> dict[str, Any]:
    """Keep existing Codex threads visible after switching model providers.

    Codex stores the provider both in rollout session_meta records and in the
    threads table. This mirrors EasyCLIProxyAPI's provider-repair behavior.
    The caller must create a snapshot before invoking this function.
    """
    target_provider = target_provider.strip()
    if not target_provider:
        raise ValueError("Target provider cannot be empty.")

    staged: list[tuple[Path, bytes, bytes, int, str | None, str | None, bool]] = []
    thread_metadata: dict[str, tuple[str | None, bool]] = {}
    warnings: list[str] = []
    for path in collect_rollout_files(codex_home):
        try:
            repair = _rewrite_rollout_provider(path, target_provider)
        except (OSError, UnicodeError) as exc:
            warnings.append(f"Skipped session file {path}: {exc}")
            continue
        if repair is None:
            continue
        original, updated, thread_id, cwd, has_user_event = repair
        if thread_id:
            thread_metadata[thread_id] = (cwd, has_user_event)
        if updated != original:
            modified_ns = path.stat().st_mtime_ns
            staged.append((path, original, updated, modified_ns, thread_id, cwd, has_user_event))

    written: list[tuple[Path, bytes, int]] = []
    try:
        for path, original, updated, modified_ns, _thread_id, _cwd, _has_user_event in staged:
            _atomic_write_bytes(path, updated)
            os.utime(path, ns=(modified_ns, modified_ns))
            written.append((path, original, modified_ns))

        sqlite_rows_updated = 0
        for database in discover_session_databases(sqlite_home):
            try:
                connection = sqlite3.connect(database, timeout=5.0)
                try:
                    columns = {
                        row[1]
                        for row in connection.execute('PRAGMA table_info("threads")')
                    }
                    if not columns:
                        continue
                    if "model_provider" in columns:
                        cursor = connection.execute(
                            "UPDATE threads SET model_provider = ? WHERE COALESCE(model_provider, '') <> ?",
                            (target_provider, target_provider),
                        )
                        sqlite_rows_updated += max(cursor.rowcount, 0)
                    for thread_id, (cwd, has_user_event) in thread_metadata.items():
                        if has_user_event and "has_user_event" in columns:
                            cursor = connection.execute(
                                "UPDATE threads SET has_user_event = 1 WHERE id = ? AND COALESCE(has_user_event, 0) <> 1",
                                (thread_id,),
                            )
                            sqlite_rows_updated += max(cursor.rowcount, 0)
                        if cwd and "cwd" in columns:
                            cursor = connection.execute(
                                "UPDATE threads SET cwd = ? WHERE id = ? AND COALESCE(cwd, '') <> ?",
                                (cwd, thread_id, cwd),
                            )
                            sqlite_rows_updated += max(cursor.rowcount, 0)
                    connection.commit()
                finally:
                    connection.close()
            except sqlite3.Error as exc:
                warnings.append(f"Skipped session database {database}: {exc}")
    except Exception:
        for path, original, modified_ns in reversed(written):
            try:
                _atomic_write_bytes(path, original)
                os.utime(path, ns=(modified_ns, modified_ns))
            except OSError:
                pass
        raise

    return {
        "rollout_files_updated": len(written),
        "sqlite_rows_updated": sqlite_rows_updated,
        "warnings": warnings,
    }


def http_get_json(url: str, api_key: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": f"{APP_NAME}/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read().decode("utf-8", errors="replace")
    return json.loads(data)


def runtime_models_from_payload(payload: Any) -> list[RuntimeModel]:
    values: list[Any] = []
    if isinstance(payload, dict):
        candidate = payload.get("models") or payload.get("data")
        if isinstance(candidate, list):
            values = candidate
    elif isinstance(payload, list):
        values = payload

    models: list[RuntimeModel] = []
    seen: set[str] = set()
    for value in values:
        slug = ""
        if isinstance(value, str):
            slug = value.strip()
        elif isinstance(value, dict):
            for key in ("slug", "id", "name", "model", "value"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    slug = candidate.strip()
                    break
        if not slug:
            continue
        normalized = slug.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        display_name = None
        description = None
        context_window = None
        max_context_window = None
        input_modalities = None
        supported_reasoning_levels = None
        default_reasoning_level = None
        hidden = False
        if isinstance(value, dict):
            for key in ("display_name", "displayName"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    display_name = candidate.strip()
                    break
            for key in ("description",):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    description = candidate.strip()
                    break
            for key in ("context_window", "contextWindow", "context_length", "contextLength"):
                candidate = value.get(key)
                if isinstance(candidate, (int, float)) and candidate > 0:
                    context_window = int(candidate)
                    break
            for key in ("max_context_window", "maxContextWindow"):
                candidate = value.get(key)
                if isinstance(candidate, (int, float)) and candidate > 0:
                    max_context_window = int(candidate)
                    break
            raw_modalities = value.get("input_modalities")
            if isinstance(raw_modalities, list):
                input_modalities = sorted(
                    {
                        str(item).strip().lower()
                        for item in raw_modalities
                        if str(item).strip().lower() in {"text", "image"}
                    }
                )
                if not input_modalities:
                    input_modalities = None
            raw_levels = value.get("supported_reasoning_levels")
            if isinstance(raw_levels, list):
                levels = []
                for item in raw_levels:
                    if isinstance(item, str) and item.strip():
                        level = item.strip().lower()
                    elif isinstance(item, dict) and isinstance(item.get("effort"), str):
                        level = item["effort"].strip().lower()
                    else:
                        continue
                    if level in {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"} and level not in levels:
                        levels.append(level)
                supported_reasoning_levels = levels or None
            for key in ("default_reasoning_level", "defaultReasoningLevel"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    default_reasoning_level = candidate.strip().lower()
                    break
            if isinstance(value.get("visibility"), str) and value["visibility"].lower() == "hide":
                hidden = True
        models.append(
            RuntimeModel(
                slug=slug,
                display_name=display_name,
                description=description,
                context_window=context_window,
                max_context_window=max_context_window,
                input_modalities=input_modalities,
                supported_reasoning_levels=supported_reasoning_levels,
                default_reasoning_level=default_reasoning_level,
                hidden=hidden,
            )
        )
    return models


def fetch_runtime_models(base_url: str, api_key: str) -> list[RuntimeModel]:
    urls = [f"{base_url}/models", base_url.replace("/v1", "") + "/models" if base_url.endswith("/v1") else f"{base_url}/models"]
    errors: list[str] = []
    for url in dict.fromkeys(urls):
        try:
            payload = http_get_json(url, api_key)
            return runtime_models_from_payload(payload)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("Unable to fetch the model list:\n" + "\n".join(errors))


def load_template_catalog() -> dict[str, Any]:
    return json.loads(TEMPLATE_CATALOG_PATH.read_text(encoding="utf-8"))


def template_model_map(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for model in template.get("models", []):
        if isinstance(model, dict) and isinstance(model.get("slug"), str):
            result[model["slug"].lower()] = model
    return result


def apply_runtime_model_metadata(model: dict[str, Any], runtime: RuntimeModel) -> None:
    model["slug"] = runtime.slug
    model["display_name"] = runtime.display_name or runtime.slug
    if runtime.description:
        model["description"] = runtime.description
    if runtime.context_window:
        model["context_window"] = runtime.context_window
        model["max_context_window"] = max(runtime.max_context_window or runtime.context_window, runtime.context_window)
    elif runtime.max_context_window:
        model["max_context_window"] = max(runtime.max_context_window, int(model.get("context_window") or 128000))
    if runtime.input_modalities:
        model["input_modalities"] = runtime.input_modalities
        model["supports_image_detail_original"] = "image" in runtime.input_modalities
    if runtime.supported_reasoning_levels:
        model["supported_reasoning_levels"] = [
            {
                "effort": effort,
                "description": {
                    "none": "No reasoning",
                    "minimal": "Minimal reasoning",
                    "low": "Fast responses with lighter reasoning",
                    "medium": "Balances speed and reasoning depth for everyday tasks",
                    "high": "Greater reasoning depth for complex problems",
                    "xhigh": "Extra high reasoning depth for complex problems",
                    "max": "Maximum available reasoning depth for complex problems",
                    "ultra": "Highest available reasoning depth",
                }.get(effort, "Model-supported reasoning level"),
            }
            for effort in runtime.supported_reasoning_levels
        ]
        if runtime.default_reasoning_level in runtime.supported_reasoning_levels:
            model["default_reasoning_level"] = runtime.default_reasoning_level
    if runtime.hidden:
        model["visibility"] = "hide"


def build_catalog(template: dict[str, Any], runtime_models: list[RuntimeModel], selected_model: str | None) -> str:
    fallback = json.loads(json.dumps(template["fallback_model"]))
    templates = template_model_map(template)

    models: list[dict[str, Any]] = []
    selected_normalized = selected_model.lower().strip() if selected_model else None
    if runtime_models:
        for runtime in runtime_models:
            key = runtime.slug.lower()
            if key in templates:
                entry = json.loads(json.dumps(templates[key]))
            else:
                entry = json.loads(json.dumps(fallback))
                apply_runtime_model_metadata(entry, runtime)
            entry["slug"] = runtime.slug
            if runtime.display_name:
                entry["display_name"] = runtime.display_name
            if runtime.description:
                entry["description"] = runtime.description
            models.append(entry)
        if selected_normalized and all(model["slug"].lower() != selected_normalized for model in models):
            entry = json.loads(json.dumps(fallback))
            apply_runtime_model_metadata(
                entry,
                RuntimeModel(slug=selected_model, display_name=selected_model, context_window=entry.get("context_window", 128000)),
            )
            models.insert(0, entry)
    else:
        models = [json.loads(json.dumps(model)) for model in template.get("models", [])]
    return json.dumps({"fallback_model": fallback, "models": models}, ensure_ascii=False, indent=2) + "\n"


def locate_model_catalog_path(codex_home: Path) -> Path:
    return codex_home / MANAGED_CATALOG_FILE


def patch_codex_config(
    existing_text: str | None,
    base_url: str,
    api_key: str,
    model: str,
    provider_name: str = DEFAULT_PROVIDER_NAME,
) -> str:
    model = model.strip()
    provider_name = provider_name.strip() or DEFAULT_PROVIDER_NAME
    if not model:
        raise ValueError("Default model cannot be empty.")

    source = existing_text or ""
    lines = source.splitlines()
    output: list[str] = []
    in_provider = False
    provider_found = False
    provider_header = f"[model_providers.{MANAGED_PROVIDER_ID}]"
    root_key_pattern = re.compile(r'^\s*(model_provider|model|model_catalog_json)\s*=')
    section_pattern = re.compile(r'^\s*\[[^]]+\]\s*$')
    current_section: str | None = None

    def append_managed_root_block() -> None:
        block = [
            f'model_provider = "{MANAGED_PROVIDER_ID}"',
            f'model = {json.dumps(model)}',
            f'model_catalog_json = {json.dumps(MANAGED_CATALOG_FILE)}',
            "",
        ]
        output.extend(block)

    def append_provider_block() -> None:
        block = [
            provider_header,
            f'name = {json.dumps(provider_name)}',
            f'base_url = {json.dumps(base_url)}',
            'wire_api = "responses"',
            f'experimental_bearer_token = {json.dumps(api_key)}',
            "",
        ]
        output.extend(block)

    managed_root_inserted = False
    provider_block_written = False
    for line in lines:
        stripped = line.strip()
        is_section = bool(section_pattern.match(line))
        if is_section:
            if in_provider and stripped != provider_header:
                in_provider = False
            current_section = stripped
            if stripped == provider_header:
                if not managed_root_inserted:
                    append_managed_root_block()
                    managed_root_inserted = True
                if provider_found:
                    in_provider = True
                    continue
                provider_found = True
                in_provider = True
                append_provider_block()
                provider_block_written = True
                continue
            if not managed_root_inserted:
                append_managed_root_block()
                managed_root_inserted = True
            output.append(line)
            continue

        if in_provider:
            continue
        if current_section is None and root_key_pattern.match(line):
            continue
        output.append(line)

    if not managed_root_inserted:
        append_managed_root_block()
        managed_root_inserted = True
    if not provider_block_written:
        if output and output[-1].strip():
            output.append("")
        append_provider_block()

    rendered = "\n".join(output).rstrip() + "\n"
    try:
        tomllib = __import__("tomllib")
        tomllib.loads(rendered)
    except Exception:
        pass
    return rendered


def find_snapshot_dirs() -> list[Path]:
    ensure_directories()
    snapshots = [path for path in BACKUP_DIR.iterdir() if path.is_dir()]
    snapshots.sort(reverse=True)
    return snapshots


def describe_snapshot(snapshot_dir: Path) -> str:
    metadata = load_snapshot_metadata(snapshot_dir)
    created = metadata.get("createdAt", snapshot_dir.name)
    reason = metadata.get("reason", "")
    return f"{created}  {reason}".strip()


class AppUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("980x700")
        self.root.minsize(920, 640)
        self.work_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.codex_home_var = tk.StringVar(value=str(resolve_codex_home()))
        self.sqlite_home_var = tk.StringVar(value=str(resolve_codex_sqlite_home(Path(self.codex_home_var.get()))))
        self.base_url_var = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.model_status_var = tk.StringVar(value="Not detected")
        self.snapshot_status_var = tk.StringVar(value="")
        self.snapshot_items: list[Path] = []
        self.detected_models: list[str] = []
        self.model_selector: ttk.Combobox | None = None
        self._loading_settings = False
        self._build()
        self._load_settings()
        self.base_url_var.trace_add("write", self._on_settings_changed)
        self.api_key_var.trace_add("write", self._on_settings_changed)
        self.model_var.trace_add("write", self._on_settings_changed)
        self.refresh_snapshots()

    def _build(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        path_frame = ttk.LabelFrame(frame, text="Codex Paths")
        path_frame.grid(row=0, column=0, sticky="ew")
        path_frame.columnconfigure(1, weight=1)
        ttk.Label(path_frame, text="CODEX_HOME").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(path_frame, textvariable=self.codex_home_var).grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(path_frame, text="Refresh", command=self.refresh_paths).grid(row=0, column=2, sticky="e", padx=8, pady=6)
        ttk.Label(path_frame, text="CODEX_SQLITE_HOME").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(path_frame, textvariable=self.sqlite_home_var).grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ttk.Label(path_frame, text="Paths are read from environment variables by default. You can override them manually.").grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 8))

        notebook = ttk.Notebook(frame)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        notebook.add(self._build_config_tab(notebook), text="Settings")
        notebook.add(self._build_backup_tab(notebook), text="Backup & Restore")

        status = ttk.Frame(frame)
        status.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        self.root.after(150, self._poll_queue)

    def _build_config_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)
        tab.columnconfigure(1, weight=1)

        ttk.Label(tab, text="Responses API Base URL").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(tab, textvariable=self.base_url_var).grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        ttk.Label(tab, text="API Key").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(tab, textvariable=self.api_key_var, show="*").grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ttk.Label(tab, text="Default Model").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        self.model_selector = ttk.Combobox(tab, textvariable=self.model_var, state="readonly", values=[])
        self.model_selector.grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        ttk.Button(tab, text="Detect Models", command=self.detect_models).grid(row=2, column=2, sticky="e", padx=6, pady=6)
        ttk.Label(tab, textvariable=self.model_status_var).grid(row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 8))

        button_row = ttk.Frame(tab)
        button_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=6, pady=6)
        ttk.Button(button_row, text="Apply to Codex", command=self.apply_configuration).pack(side="left")
        ttk.Button(button_row, text="Create Snapshot Only", command=self.create_manual_snapshot).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="Restore Latest Snapshot", command=self.restore_latest_snapshot).pack(side="left", padx=(8, 0))
        return tab

    def _build_backup_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        self.snapshot_list = tk.Listbox(tab, height=14)
        self.snapshot_list.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.snapshot_list.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.snapshot_list.configure(yscrollcommand=scroll.set)

        top = ttk.Frame(tab)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(top, text="Select a snapshot to restore. A snapshot includes Codex config and local session data.").pack(side="left")

        actions = ttk.Frame(tab)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(4, 0))
        ttk.Button(actions, text="Refresh List", command=self.refresh_snapshots).pack(side="left")
        ttk.Button(actions, text="Restore Selected Snapshot", command=self.restore_selected_snapshot).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open Backup Folder", command=self.open_backup_dir).pack(side="left", padx=(8, 0))
        ttk.Label(tab, textvariable=self.snapshot_status_var).grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))
        return tab

    def refresh_paths(self) -> None:
        codex_home = expand_path(self.codex_home_var.get())
        sqlite_home = expand_path(self.sqlite_home_var.get())
        self.codex_home_var.set(str(codex_home))
        self.sqlite_home_var.set(str(sqlite_home))
        self.status_var.set(f"Paths refreshed: {codex_home}")

    def current_paths(self) -> tuple[Path, Path]:
        codex_home = expand_path(self.codex_home_var.get())
        sqlite_home = expand_path(self.sqlite_home_var.get())
        return codex_home, sqlite_home

    def _load_settings(self) -> None:
        self._loading_settings = True
        try:
            settings = load_settings()
            if settings.get("base_url"):
                self.base_url_var.set(settings["base_url"])
            if settings.get("api_key"):
                self.api_key_var.set(settings["api_key"])
            if settings.get("model"):
                self.model_var.set(settings["model"])
        finally:
            self._loading_settings = False

    def _on_settings_changed(self, *_: object) -> None:
        if self._loading_settings:
            return
        try:
            save_settings({
                "base_url": self.base_url_var.get().strip(),
                "api_key": self.api_key_var.get(),
                "model": self.model_var.get().strip(),
            })
        except Exception:
            pass

    def detect_models(self) -> None:
        base_url = self.base_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        if not base_url or not api_key:
            messagebox.showerror(APP_NAME, "Please enter the Responses API base URL and API key first.")
            return

        def worker() -> None:
            try:
                effective_base = normalize_base_url(base_url)
                runtime_models = fetch_runtime_models(effective_base, api_key)
                self.work_queue.put(("models", (effective_base, runtime_models)))
            except Exception as exc:
                self.work_queue.put(("error", f"Model detection failed: {exc}"))

        self.status_var.set("Detecting models...")
        threading.Thread(target=worker, daemon=True).start()

    def apply_configuration(self) -> None:
        base_url = self.base_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()
        if not base_url or not api_key or not model:
            messagebox.showerror(APP_NAME, "Please enter the API URL, API key, and default model.")
            return

        codex_home, sqlite_home = self.current_paths()

        def worker() -> None:
            try:
                effective_base = normalize_base_url(base_url)
                snapshot_dir = create_snapshot(codex_home, sqlite_home, "before-apply")
                template = load_template_catalog()
                runtime_models = []
                try:
                    runtime_models = fetch_runtime_models(effective_base, api_key)
                except Exception:
                    runtime_models = []
                catalog = build_catalog(template, runtime_models, model)
                target_config = codex_home / "config.toml"
                target_catalog = locate_model_catalog_path(codex_home)
                original = read_text(target_config)
                patched = patch_codex_config(original, effective_base, api_key, model)
                write_text(target_config, patched)
                write_text(target_catalog, catalog)
                repair = repair_session_provider_metadata(codex_home, sqlite_home)
                warning_count = len(repair["warnings"])
                self.work_queue.put((
                    "info",
                    "Configuration applied successfully. Existing conversations were synchronized "
                    f"({repair['rollout_files_updated']} session files, "
                    f"{repair['sqlite_rows_updated']} database rows). "
                    f"Snapshot saved: {snapshot_dir}"
                    + (f" {warning_count} item(s) were skipped; close Codex and apply again." if warning_count else "")
                    + "\n\nPlease fully restart Codex for the new configuration and conversations to load correctly.",
                ))
            except Exception as exc:
                self.work_queue.put(("error", f"Apply failed: {exc}"))

        self.status_var.set("Applying configuration...")
        threading.Thread(target=worker, daemon=True).start()

    def create_manual_snapshot(self) -> None:
        codex_home, sqlite_home = self.current_paths()

        def worker() -> None:
            try:
                snapshot_dir = create_snapshot(codex_home, sqlite_home, "manual")
                self.work_queue.put(("info", f"Snapshot created: {snapshot_dir}"))
            except Exception as exc:
                self.work_queue.put(("error", f"Snapshot creation failed: {exc}"))

        self.status_var.set("Creating snapshot...")
        threading.Thread(target=worker, daemon=True).start()

    def restore_latest_snapshot(self) -> None:
        snapshots = find_snapshot_dirs()
        if not snapshots:
            messagebox.showinfo(APP_NAME, "No snapshots are available to restore.")
            return
        self._restore_snapshot(snapshots[0])

    def restore_selected_snapshot(self) -> None:
        selection = self.snapshot_list.curselection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Please select a snapshot first.")
            return
        snapshot_dir = self.snapshot_items[selection[0]]
        self._restore_snapshot(snapshot_dir)

    def _restore_snapshot(self, snapshot_dir: Path) -> None:
        confirmed = messagebox.askokcancel(
            APP_NAME,
            "Before restoring, completely close Codex. Open Codex processes may lock session files "
            "and prevent a complete restore.\n\nClick OK only after Codex has been closed.",
            icon="warning",
        )
        if not confirmed:
            self.status_var.set("Restore cancelled. Close Codex before trying again.")
            return

        codex_home, sqlite_home = self.current_paths()

        def worker() -> None:
            try:
                restored = restore_snapshot(snapshot_dir, codex_home, sqlite_home)
                self.work_queue.put((
                    "info",
                    f"Snapshot restored successfully: {snapshot_dir} ({len(restored)} files)"
                    "\n\nYou can now start Codex again.",
                ))
            except Exception as exc:
                self.work_queue.put(("error", f"Restore failed: {exc}"))

        self.status_var.set("Restoring snapshot...")
        threading.Thread(target=worker, daemon=True).start()

    def refresh_snapshots(self) -> None:
        snapshots = find_snapshot_dirs()
        self.snapshot_items = snapshots
        self.snapshot_list.delete(0, tk.END)
        for snapshot in snapshots:
            self.snapshot_list.insert(tk.END, describe_snapshot(snapshot))
        self.snapshot_status_var.set(f"{len(snapshots)} snapshot(s) found")

    def open_backup_dir(self) -> None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(BACKUP_DIR)  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Unable to open the backup folder: {exc}")

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.work_queue.get_nowait()
                if kind == "models":
                    effective_base, runtime_models = payload
                    models = [model.slug for model in runtime_models]
                    self.base_url_var.set(effective_base.rsplit("/v1", 1)[0] if effective_base.endswith("/v1") else effective_base)
                    if models:
                        if self.model_selector is not None:
                            self.model_selector["values"] = models
                        current_model = self.model_var.get().strip()
                        self.model_var.set(current_model if current_model in models else models[0])
                        self.model_status_var.set(f"Detected {len(models)} model(s). Choose one from the dropdown.")
                    else:
                        if self.model_selector is not None:
                            self.model_selector["values"] = []
                        self.model_var.set("")
                        self.model_status_var.set("No models detected.")
                    self.status_var.set("Model detection complete.")
                elif kind == "info":
                    self.status_var.set(str(payload))
                    self.refresh_snapshots()
                    messagebox.showinfo(APP_NAME, str(payload))
                elif kind == "error":
                    self.status_var.set(str(payload))
                    messagebox.showerror(APP_NAME, str(payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(150, self._poll_queue)


def main() -> None:
    ensure_directories()
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    AppUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

