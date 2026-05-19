# Docs tools

## Structurizr workspace watcher (dev only)

This watcher monitors configured `workspace.dsl` files and pushes updates to a Structurizr server whenever a file changes.
It can also auto-provision missing workspace credentials (`id`, `key`, optional `secret`) and persist them into your local settings file.

### Files

- `structurizr_watch_push.py`: watcher/pusher script.
- `structurizr.watch.dev.template.json`: committed template with placeholders only.
- `structurizr.watch.dev.json`: local, **dev-only** settings file (gitignored).

### Setup

1. Create your local config from the template.
2. Choose a push style:
   - `legacy`: uses `id + key + secret` (older server/CLI behavior)
   - `modern`: uses `id + key` (recommended for Structurizr vNext server API)
3. If you want auto-provisioning, leave workspace credentials empty and set `provisioning.admin_api_key` when required by your server.
4. Keep `"dev_only": true`.
### Run

From repository root:

- `python3 docs/tools/structurizr_watch_push.py --push-on-start`

Without `--push-on-start`, the script waits for the first file change before pushing.

### Config notes

Top-level settings:

- `server_url`: Structurizr base URL (e.g. `http://localhost:8081`)
- `api_url`: Structurizr API URL (e.g. `http://localhost:8081/api`)

`workspaces[]` supports:

- `type`: `enterprise` or `cap`
- `capability`: optional, useful label for `cap`
- `dsl`: path to the `workspace.dsl`
- `id`, `key`, `secret`: Structurizr workspace credentials

`provisioning` supports:

- `enabled`: allow auto-provisioning of missing credentials.
- `create_if_missing`: create workspace if `id` is missing.
- `regenerate_key_if_missing`: generate key if missing.
- `admin_api_key`: admin API key used for provisioning calls.
- `persist_updates`: write generated credentials back to `structurizr.watch.dev.json`.
- `require_secret`: fail if no `secret` is available (useful in strict legacy setups).
- `allow_unsupported_admin_api`: if true, returns a clear error when the server disables admin API (e.g. open-core).
- `try_web_create_fallback`: when admin API workspace creation is unavailable, try creating via `/workspace/create` and extract the new workspace ID from redirect URL.

Notes:

- If `admin_api_key` is empty, the script can still auto-fill workspace `id` (via admin API or web fallback) but cannot auto-regenerate a missing `key`.
- `manual_fallback_mode`: what to do when auto-provisioning fails:
	- `none`: no fallback, fail immediately
	- `print`: print direct manual steps per workspace
	- `open`: open the relevant Structurizr page in a browser
	- `print_and_open`: both print and open

CLI modes:

- `docker` (default): runs `structurizr/structurizr:latest` via Docker.
- `native`: uses local command from `cli.command` (default `structurizr`).

Docker CLI options:

- `docker_network_mode`: `host` or `bridge` (default `host`).
	- Use `host` on Linux when your Structurizr server is on `http://localhost:8081`.

### Important note about open-core servers

Some Structurizr server distributions disable the admin API. In that case, auto-creation of workspaces is not possible via API, and you must create workspaces manually first, then fill or keep credentials in your local dev settings.
