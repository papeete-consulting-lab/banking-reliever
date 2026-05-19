#!/usr/bin/env python3
"""Watch Structurizr DSL files and push updated workspaces to a Structurizr server.

This tool is intentionally for local development usage.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CliConfig:
    mode: str
    command: str
    docker_image: str
    push_style: str
    docker_network_mode: str


@dataclass(frozen=True)
class ProvisioningConfig:
    enabled: bool
    create_if_missing: bool
    regenerate_key_if_missing: bool
    admin_api_key: str
    persist_updates: bool
    require_secret: bool
    allow_unsupported_admin_api: bool
    manual_fallback_mode: str
    try_web_create_fallback: bool


@dataclass(frozen=True)
class WorkspaceConfig:
    type: str
    dsl: Path
    workspace_id: str
    key: str
    secret: str
    source_index: int
    capability: str | None = None


@dataclass(frozen=True)
class WatchConfig:
    dev_only: bool
    server_url: str
    api_url: str
    poll_interval_seconds: float
    debounce_seconds: float
    cli: CliConfig
    provisioning: ProvisioningConfig
    workspaces: list[WorkspaceConfig]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch Structurizr DSL files and push to Structurizr on changes."
    )
    parser.add_argument(
        "--config",
        default="docs/tools/structurizr.watch.dev.json",
        help=(
            "Path to the local dev settings file (gitignored). "
            "Default: docs/tools/structurizr.watch.dev.json"
        ),
    )
    parser.add_argument(
        "--push-on-start",
        action="store_true",
        help="Push all configured workspaces once before entering watch mode.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Settings file not found: {path}\n"
            "Create it from docs/tools/structurizr.watch.dev.template.json"
        ) from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in settings file {path}: {exc}") from exc


def _normalize_api_url(server_url: str, api_url: str) -> str:
    normalized = api_url.strip() if api_url.strip() else server_url.strip()
    if not normalized:
        return normalized

    normalized = normalized.rstrip("/")
    if not normalized.endswith("/api"):
        normalized = f"{normalized}/api"
    return normalized


def _is_admin_api_unsupported(message: str) -> bool:
    text = (message or "").lower()
    return "admin api is not supported in the open core version" in text


def _extract_field(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        value_as_str = str(value).strip()
        if value_as_str:
            return value_as_str
    return ""


def _http_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    payload = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=payload, method=method)
    for k, v in request_headers.items():
        request.add_header(k, v)

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.getcode()
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"HTTP request failed for {url}: {exc.reason}") from exc

    raw = raw.strip()
    if not raw:
        return status, {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return status, {"raw": raw}

    if isinstance(parsed, dict):
        return status, parsed

    return status, {"data": parsed}


def _http_get_final_url(url: str) -> tuple[int, str, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.getcode()
            final_url = response.geturl() or url
            raw = response.read().decode("utf-8", errors="replace")
            return status, final_url, raw
    except urllib.error.HTTPError as exc:
        status = exc.code
        final_url = exc.geturl() or url
        raw = exc.read().decode("utf-8", errors="replace")
        return status, final_url, raw
    except urllib.error.URLError as exc:
        raise RuntimeError(f"HTTP request failed for {url}: {exc.reason}") from exc


def _extract_workspace_id_from_url(url: str) -> str:
    match = re.search(r"/workspace/(\d+)", url)
    return match.group(1) if match else ""


def _save_json(path: Path, content: dict[str, Any]) -> None:
    path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")


def _run_cli_command(
    cfg: WatchConfig,
    repo_root: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    if cfg.cli.mode == "native":
        base_cmd = shlex.split(cfg.cli.command)
        if not base_cmd:
            raise RuntimeError("cli.command is empty")
        command = [*base_cmd, *args]
    else:
        command = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{repo_root.resolve()}:/workspace",
            "-w",
            "/workspace",
            cfg.cli.docker_image,
            *args,
        ]

    return subprocess.run(command, check=True, capture_output=True, text=True)


def _provision_workspace(
    workspace: WorkspaceConfig,
    cfg: WatchConfig,
) -> tuple[str, str, str, bool]:
    workspace_id = workspace.workspace_id.strip()
    key = workspace.key.strip()
    secret = workspace.secret.strip()
    changed = False

    if not cfg.provisioning.enabled:
        return workspace_id, key, secret, changed

    headers: dict[str, str] = {}
    if cfg.provisioning.admin_api_key:
        headers["X-Authorization"] = cfg.provisioning.admin_api_key

    label = workspace.capability or workspace.type

    if not workspace_id and cfg.provisioning.create_if_missing:
        status, body = _http_json("POST", f"{cfg.api_url}/workspace", headers=headers)
        message = _extract_field(body, ["message", "error"])
        if status != 200:
            if cfg.provisioning.allow_unsupported_admin_api and _is_admin_api_unsupported(message):
                if cfg.provisioning.try_web_create_fallback:
                    create_url = _manual_create_url(cfg)
                    web_status, final_url, raw = _http_get_final_url(create_url)
                    workspace_id = _extract_workspace_id_from_url(final_url)
                    if not workspace_id:
                        workspace_id = _extract_workspace_id_from_url(raw)

                    if workspace_id:
                        changed = True
                        print(
                            f"[provision] [{label}] Created workspace via web fallback with id={workspace_id}",
                            flush=True,
                        )
                    else:
                        raise RuntimeError(
                            "Admin API unsupported and web fallback did not return a workspace id "
                            f"(HTTP {web_status}, url={final_url})."
                        )
                else:
                    raise RuntimeError(
                        "Admin API is disabled on this Structurizr server (open-core). "
                        f"Cannot auto-create workspace for [{label}]."
                    )
            else:
                raise RuntimeError(
                    f"Workspace creation failed for [{label}] (HTTP {status}): {message or body}"
                )
        else:
            workspace_id = _extract_field(body, ["id", "workspaceId"])
            key = _extract_field(body, ["apiKey", "key"]) or key
            secret = _extract_field(body, ["apiSecret", "secret"]) or secret

            if not workspace_id:
                raise RuntimeError(
                    f"Workspace creation returned no workspace id for [{label}]: {body}"
                )

            changed = True
            print(f"[provision] [{label}] Created workspace with id={workspace_id}", flush=True)

    if workspace_id and not key and cfg.provisioning.regenerate_key_if_missing:
        if not cfg.provisioning.admin_api_key:
            print(
                f"[warn] [{label}] key is empty and provisioning.admin_api_key is not set; cannot auto-regenerate key.",
                flush=True,
            )
            return workspace_id, key, secret, changed

        status, body = _http_json(
            "POST",
            f"{cfg.api_url}/workspace/{workspace_id}/apikey/regenerate",
            headers=headers,
        )
        message = _extract_field(body, ["message", "error"])
        if status != 200:
            raise RuntimeError(
                f"API key regeneration failed for [{label}] (HTTP {status}): {message or body}"
            )

        key = _extract_field(body, ["apiKey", "key"])
        if not key:
            raise RuntimeError(
                f"API key regeneration returned no apiKey for [{label}]: {body}"
            )

        secret = _extract_field(body, ["apiSecret", "secret"]) or secret
        changed = True
        print(f"[provision] [{label}] Regenerated API key", flush=True)

    if cfg.provisioning.require_secret and not secret:
        raise RuntimeError(
            f"[{label}] secret is missing and provisioning.require_secret=true"
        )

    return workspace_id, key, secret, changed


def _manual_create_url(cfg: WatchConfig) -> str:
    return f"{cfg.server_url.rstrip('/')}/workspace/create"


def _manual_settings_url(cfg: WatchConfig, workspace_id: str) -> str:
    return f"{cfg.server_url.rstrip('/')}/workspace/{workspace_id}/settings"


def _open_url(url: str) -> None:
    try:
        opened = webbrowser.open(url, new=2)
        if not opened:
            print(f"[manual] Could not auto-open browser for: {url}", flush=True)
    except Exception as exc:  # pragma: no cover - defensive best effort
        print(f"[manual] Browser open failed for {url}: {exc}", flush=True)


def _print_manual_steps(
    workspace: WorkspaceConfig,
    cfg: WatchConfig,
    reason: str,
) -> None:
    label = workspace.capability or workspace.type
    dsl_display = workspace.dsl
    push_style = cfg.cli.push_style

    print("", flush=True)
    print(f"[manual] Workspace setup required for [{label}]", flush=True)
    print(f"[manual] Reason: {reason}", flush=True)
    print(f"[manual] DSL: {dsl_display}", flush=True)

    if workspace.workspace_id:
        settings_url = _manual_settings_url(cfg, workspace.workspace_id)
        print("[manual] Steps:", flush=True)
        print(f"  1) Open workspace settings: {settings_url}", flush=True)
        print(
            "  2) Regenerate/copy the API key and paste into workspaces[].key",
            flush=True,
        )
        if push_style == "legacy":
            print(
                "  3) If your server requires a secret, paste it into workspaces[].secret",
                flush=True,
            )
        print(
            "  4) Re-run: python3 docs/tools/structurizr_watch_push.py --push-on-start",
            flush=True,
        )
    else:
        create_url = _manual_create_url(cfg)
        print("[manual] Steps:", flush=True)
        print(f"  1) Open workspace creation page: {create_url}", flush=True)
        print(
            "  2) Create a new workspace and copy the generated workspace id",
            flush=True,
        )
        print(
            "  3) Open /workspace/{id}/settings and copy/regenerate API key",
            flush=True,
        )
        if push_style == "legacy":
            print(
                "  4) If applicable, copy the workspace secret for legacy push",
                flush=True,
            )
        print(
            "  5) Update this config entry: id/key(/secret), then re-run watcher",
            flush=True,
        )


def _handle_manual_fallback(
    workspace: WorkspaceConfig,
    cfg: WatchConfig,
    reason: str,
) -> bool:
    mode = cfg.provisioning.manual_fallback_mode
    if mode == "none":
        return False

    should_print = mode in {"print", "print_and_open", "open"}
    should_open = mode in {"open", "print_and_open"}

    if should_print:
        _print_manual_steps(workspace, cfg, reason)

    if should_open:
        if workspace.workspace_id:
            _open_url(_manual_settings_url(cfg, workspace.workspace_id))
        else:
            _open_url(_manual_create_url(cfg))

    return True


def _load_config(config_path: Path, repo_root: Path) -> WatchConfig:
    raw = _read_json(config_path)

    dev_only = bool(raw.get("dev_only", False))
    if not dev_only:
        raise SystemExit(
            "Refusing to run because settings file is not marked as dev-only "
            "(expected dev_only=true)."
        )

    server_url = str(raw.get("server_url", "")).strip()
    if not server_url:
        raise SystemExit("Missing required setting: server_url")

    api_url = _normalize_api_url(server_url, str(raw.get("api_url", "")))
    if not api_url:
        raise SystemExit("Missing required setting: api_url/server_url")

    poll_interval_seconds = float(raw.get("poll_interval_seconds", 1.0))
    debounce_seconds = float(raw.get("debounce_seconds", 1.5))

    cli_raw = raw.get("cli", {})
    cli_mode = str(cli_raw.get("mode", "docker")).strip().lower()
    if cli_mode not in {"docker", "native"}:
        raise SystemExit("cli.mode must be one of: docker, native")

    cli_command = str(cli_raw.get("command", "structurizr.sh")).strip()
    docker_image = str(
        cli_raw.get("docker_image", "structurizr/structurizr:latest")
    ).strip()
    push_style = str(cli_raw.get("push_style", "legacy")).strip().lower()
    if push_style not in {"legacy", "modern"}:
        raise SystemExit("cli.push_style must be one of: legacy, modern")

    cli = CliConfig(
        mode=cli_mode,
        command=cli_command,
        docker_image=docker_image,
        push_style=push_style,
        docker_network_mode=str(cli_raw.get("docker_network_mode", "host"))
        .strip()
        .lower(),
    )

    if cli.docker_network_mode not in {"host", "bridge"}:
        raise SystemExit("cli.docker_network_mode must be one of: host, bridge")

    provisioning_raw = raw.get("provisioning", {})
    provisioning = ProvisioningConfig(
        enabled=bool(provisioning_raw.get("enabled", True)),
        create_if_missing=bool(provisioning_raw.get("create_if_missing", True)),
        regenerate_key_if_missing=bool(
            provisioning_raw.get("regenerate_key_if_missing", True)
        ),
        admin_api_key=str(provisioning_raw.get("admin_api_key", "")).strip(),
        persist_updates=bool(provisioning_raw.get("persist_updates", True)),
        require_secret=bool(provisioning_raw.get("require_secret", False)),
        allow_unsupported_admin_api=bool(
            provisioning_raw.get("allow_unsupported_admin_api", True)
        ),
        manual_fallback_mode=str(
            provisioning_raw.get("manual_fallback_mode", "print")
        )
        .strip()
        .lower(),
        try_web_create_fallback=bool(
            provisioning_raw.get("try_web_create_fallback", True)
        ),
    )

    if provisioning.manual_fallback_mode not in {
        "none",
        "print",
        "open",
        "print_and_open",
    }:
        raise SystemExit(
            "provisioning.manual_fallback_mode must be one of: "
            "none, print, open, print_and_open"
        )

    workspaces_raw = raw.get("workspaces", [])
    if not isinstance(workspaces_raw, list) or not workspaces_raw:
        raise SystemExit("workspaces must be a non-empty list")

    workspaces: list[WorkspaceConfig] = []
    for idx, item in enumerate(workspaces_raw, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"workspaces[{idx}] must be an object")

        workspace_type = str(item.get("type", "")).strip().lower()
        if workspace_type not in {"cap", "enterprise"}:
            raise SystemExit(
                f"workspaces[{idx}].type must be 'cap' or 'enterprise'"
            )

        dsl_raw = str(item.get("dsl", "")).strip()
        if not dsl_raw:
            raise SystemExit(f"workspaces[{idx}].dsl is required")

        dsl_path = Path(dsl_raw)
        if not dsl_path.is_absolute():
            dsl_path = (repo_root / dsl_path).resolve()

        workspace_id = str(item.get("id", "")).strip()
        key = str(item.get("key", "")).strip()
        secret = str(item.get("secret", "")).strip()

        capability = item.get("capability")
        capability_value = str(capability).strip() if capability is not None else None

        workspaces.append(
            WorkspaceConfig(
                type=workspace_type,
                dsl=dsl_path,
                workspace_id=workspace_id,
                key=key,
                secret=secret,
                source_index=idx - 1,
                capability=capability_value,
            )
        )

    return WatchConfig(
        dev_only=dev_only,
        server_url=server_url,
        api_url=api_url,
        poll_interval_seconds=poll_interval_seconds,
        debounce_seconds=debounce_seconds,
        cli=cli,
        provisioning=provisioning,
        workspaces=workspaces,
    )


def _push_workspace(
    workspace: WorkspaceConfig,
    cfg: WatchConfig,
    repo_root: Path,
) -> bool:
    dsl_path = workspace.dsl
    label = workspace.capability or workspace.type

    if not dsl_path.exists():
        print(f"[skip] [{label}] DSL file does not exist: {dsl_path}", flush=True)
        return False

    if not workspace.workspace_id:
        print(
            f"[error] [{label}] workspace id is missing; cannot push.",
            file=sys.stderr,
            flush=True,
        )
        return False

    push_args = [
        "push",
        "-id",
        workspace.workspace_id,
    ]

    if workspace.key:
        push_args.extend(["-key", workspace.key])

    if cfg.cli.push_style == "legacy" and workspace.secret:
        push_args.extend(["-secret", workspace.secret])

    if cfg.cli.mode == "native":
        base_cmd = shlex.split(cfg.cli.command)
        if not base_cmd:
            print("[error] cli.command is empty", file=sys.stderr, flush=True)
            return False

        push_url = cfg.server_url if cfg.cli.push_style == "legacy" else cfg.api_url
        cmd = [
            *base_cmd,
            *push_args,
            "-workspace",
            str(dsl_path),
            "-url",
            push_url,
        ]
    else:
        try:
            dsl_in_repo = dsl_path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            print(
                f"[error] [{label}] DSL file must be inside repository for docker mode: {dsl_path}",
                file=sys.stderr,
                flush=True,
            )
            return False

        push_url = cfg.server_url if cfg.cli.push_style == "legacy" else cfg.api_url
        cmd = [
            "docker",
            "run",
            "--rm",
            *( ["--network", "host"] if cfg.cli.docker_network_mode == "host" else [] ),
            "-v",
            f"{repo_root.resolve()}:/workspace",
            "-w",
            "/workspace",
            cfg.cli.docker_image,
            *push_args,
            "-workspace",
            f"/workspace/{dsl_in_repo}",
            "-url",
            push_url,
        ]

    print(
        f"[push] [{label}] {dsl_path} -> {cfg.server_url}",
        flush=True,
    )

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print(
            f"[error] Command not found while pushing [{label}]: {cmd[0]}",
            file=sys.stderr,
            flush=True,
        )
        return False
    except subprocess.CalledProcessError as exc:
        print(
            f"[error] Push failed for [{label}] with exit code {exc.returncode}",
            file=sys.stderr,
            flush=True,
        )
        return False

    print(f"[ok]   [{label}] Push successful", flush=True)
    return True


def _ensure_credentials_and_persist(
    cfg: WatchConfig,
    cfg_raw: dict[str, Any],
    cfg_path: Path,
) -> WatchConfig:
    changed = False
    unresolved_manual: list[str] = []
    new_workspaces: list[WorkspaceConfig] = []

    for workspace in cfg.workspaces:
        label = workspace.capability or workspace.type
        try:
            workspace_id, key, secret, workspace_changed = _provision_workspace(
                workspace,
                cfg,
            )
        except RuntimeError as exc:
            reason = str(exc)
            handled = _handle_manual_fallback(workspace, cfg, reason)
            if handled:
                unresolved_manual.append(label)
                new_workspaces.append(workspace)
                continue
            raise SystemExit(f"Provisioning failed for [{label}]: {reason}") from exc

        if not workspace_id:
            raise SystemExit(
                f"Missing workspace id for [{label}]. "
                "Either provide workspaces[].id or enable provisioning.create_if_missing with admin_api_key."
            )

        if not key and cfg.cli.push_style == "legacy":
            print(
                f"[warn] [{label}] key is empty; legacy push might fail on authenticated servers.",
                flush=True,
            )

        if cfg.cli.push_style == "legacy" and cfg.provisioning.require_secret and not secret:
            raise SystemExit(
                f"Missing secret for [{label}] while using legacy push with require_secret=true"
            )

        if workspace_changed:
            changed = True
            ws_raw = cfg_raw["workspaces"][workspace.source_index]
            ws_raw["id"] = workspace_id
            ws_raw["key"] = key
            ws_raw["secret"] = secret

        new_workspaces.append(
            WorkspaceConfig(
                type=workspace.type,
                dsl=workspace.dsl,
                workspace_id=workspace_id,
                key=key,
                secret=secret,
                source_index=workspace.source_index,
                capability=workspace.capability,
            )
        )

    if changed and cfg.provisioning.persist_updates:
        _save_json(cfg_path, cfg_raw)
        print(f"[config] Saved provisioned credentials to {cfg_path}", flush=True)

    if unresolved_manual:
        labels = ", ".join(unresolved_manual)
        raise SystemExit(
            "Manual workspace setup required for: "
            f"{labels}. Follow the printed steps, then re-run the watcher."
        )

    return WatchConfig(
        dev_only=cfg.dev_only,
        server_url=cfg.server_url,
        api_url=cfg.api_url,
        poll_interval_seconds=cfg.poll_interval_seconds,
        debounce_seconds=cfg.debounce_seconds,
        cli=cfg.cli,
        provisioning=cfg.provisioning,
        workspaces=new_workspaces,
    )


def _watch(cfg: WatchConfig, repo_root: Path, push_on_start: bool) -> int:
    known_mtime: dict[Path, float] = {}
    last_push_at: dict[Path, float] = {}

    for workspace in cfg.workspaces:
        try:
            known_mtime[workspace.dsl] = workspace.dsl.stat().st_mtime
        except FileNotFoundError:
            known_mtime[workspace.dsl] = -1.0

    if push_on_start:
        for workspace in cfg.workspaces:
            if _push_workspace(workspace, cfg, repo_root):
                last_push_at[workspace.dsl] = time.monotonic()

    print("[watch] Started. Press Ctrl+C to stop.", flush=True)

    while True:
        for workspace in cfg.workspaces:
            dsl = workspace.dsl
            try:
                current_mtime = dsl.stat().st_mtime
            except FileNotFoundError:
                current_mtime = -1.0

            previous_mtime = known_mtime.get(dsl, -1.0)
            if current_mtime == previous_mtime:
                continue

            known_mtime[dsl] = current_mtime
            now = time.monotonic()
            if now - last_push_at.get(dsl, 0.0) < cfg.debounce_seconds:
                continue

            if _push_workspace(workspace, cfg, repo_root):
                last_push_at[dsl] = now

        time.sleep(cfg.poll_interval_seconds)


def main() -> int:
    args = _parse_args()

    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve()

    cfg_raw = _read_json(config_path)
    cfg = _load_config(config_path, repo_root)
    cfg = _ensure_credentials_and_persist(cfg, cfg_raw, config_path)

    print("Structurizr watcher configuration:", flush=True)
    print(f"  config: {config_path}", flush=True)
    print(f"  server: {cfg.server_url}", flush=True)
    print(f"  api: {cfg.api_url}", flush=True)
    print(f"  cli mode: {cfg.cli.mode}", flush=True)
    print(f"  push style: {cfg.cli.push_style}", flush=True)
    print(f"  workspaces: {len(cfg.workspaces)}", flush=True)

    try:
        return _watch(cfg, repo_root, args.push_on_start)
    except KeyboardInterrupt:
        print("\n[watch] Stopped.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
