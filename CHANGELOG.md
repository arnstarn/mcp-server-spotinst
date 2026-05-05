# Changelog

All notable changes to this project will be documented in this file.

## [0.7.0] - 2026-05-05

### Added
- **`create_vng`** — Create an AWS Ocean VNG (launch spec) under an existing Ocean cluster.
  - `ocean_id` is a first-class argument; passing `oceanId` inside `spec_json` is rejected.
  - Plaintext `userData` is auto-base64-encoded (opt out with `encode_user_data=false`).
  - Optional `initial_nodes>0` launches that many nodes immediately.
  - Requires `confirm=true`; safety preview shown otherwise.
- **`delete_vng`** — Delete an AWS Ocean VNG (launch spec).
  - `delete_nodes=true` drains+detaches+terminates all nodes in the VNG.
  - `force_delete=true` permits deleting the only non-template VNG.
  - Requires `confirm=true`; safety preview shown otherwise.
- **`update_vng` readback-mismatch detection** — fallout from the 2026-05-05 dev triton-gpu incident, where Spot.io returned 200 OK and bumped `updatedAt` but silently did not persist the new `userData`. The tool now diffs every submitted field against the readback and surfaces any mismatch as `_readback_mismatch` with a `_readback_mismatch_hint`. `userData` is compared on decoded-plaintext bytes so benign re-encodes don't false-positive.

### Tests
- Unit tests for the readback-diff helper (`_diff_submitted_vs_readback`, `_extract_launchspec`) covering userData round-trip, silent non-persist, value drift, and nested response shapes.
- New live integration suite under `tests/integration/` (opt in with `SPOTINST_RUN_INTEGRATION=1`) that spins up an ephemeral VNG, exercises `create_vng` / `update_vng` / `delete_vng` across encoded and plaintext userData, `auto_apply_tags`, safety previews, and teardown. Excluded from default `pytest` run via `norecursedirs`.

## [0.6.0] - 2026-05-04

### Fixed
- **`update_vng` hang diagnosis** — fallout from the 2026-05-01 g3-prod GPU I/O incident, where `update_vng` stalled with no visible error and required a manual curl fallback to land the userdata fix:
  - Split httpx timeout into explicit `connect=10s`, `read=120s`, `write=120s`, `pool=10s` (was a single 30s covering all phases). Read/write timeouts overridable via `SPOTINST_HTTP_READ_TIMEOUT` / `SPOTINST_HTTP_WRITE_TIMEOUT`.
  - Wrap `httpx.TimeoutException` into `TimeoutError` with method, path, body size, and elapsed time so a hang surfaces as a loud error instead of a silent stall.
  - Emit stderr log line on every write (`POST/PUT/PATCH/DELETE`): `method path body_size=N elapsed=X.Ys status=...`. Visible in the MCP server's stderr for post-hoc diagnosis.
  - Raise `ValueError` when `accountId` is neither set via env nor passed explicitly — the Spot API spec requires it and used to fail opaquely.

### Added
- **`update_vng` auto-encodes plaintext `userData` to base64** — per the Spot API spec, `userData` must be base64-encoded. Plaintext bash scripts were the likely root cause of past silent failures. New `encode_user_data=true` parameter (default) base64-encodes when input doesn't already look like base64; set `false` to pass through as-is.
- **`update_vng` post-update read-back** — the tool now returns `{put_result, readback}` so callers can verify the change actually landed. Readback errors are captured into `_readback_error` without re-raising.
- **`update_vng` `auto_apply_tags` parameter** — maps to the Spot API's `autoApplyTags` query param; updates tags without triggering a roll.

### Changed
- Stderr logging is emitted only for write operations (reads stay quiet to avoid log spam).

### Tests
- Added 10 tests: `update_vng_with_auto_apply_tags`, `update_vng_requires_account_id`, `update_vng_wraps_timeout`, `timeout_respects_env_override`, `looks_like_base64`, `update_vng_auto_encodes_userdata`, `update_vng_skips_encode_when_already_base64`, `update_vng_opt_out_encoding`, `update_vng_returns_readback`, `update_vng_readback_error_captured` (92 total).

## [0.5.0] - 2026-03-23

### Added
- **Write permission probing** in `probe_token_capabilities` — distinguishes read-only tokens from read+write tokens:
  - Probes `roll` and `detach` endpoints using real cluster IDs with fake instance IDs (safe dry-run)
  - Detects Spot.io's non-standard permission denials (400 "An unknown error occurred" instead of 403)
  - Response now includes `read_access`, `write_access`, `write_denied` fields
  - Recommendation summary: "full read + write", "read-only", or "partial write"
- 4 new probe tests (82 total)

### Changed
- CI workflows bumped to `actions/checkout@v6` and `actions/setup-python@v6` (Node.js 24)

## [0.4.1] - 2026-03-23

### Fixed
- **`get_cluster_costs` / `get_cost_trending` docstring** — removed invalid `resource` option from `group_by` docs; only `namespace` is supported by the API

### Added
- **Smart response truncation** with `limit` parameter on tools that return large unbounded lists:
  - **`get_right_sizing`** — sorted by savings potential (biggest CPU delta first), default top 50
  - **`get_cluster_nodes`** — default 50
  - **`get_cluster_costs`** — namespace aggregations sorted by cost descending, default top 50
- `limit=0` disables truncation and returns all results (full opt-out)
- Truncation metadata (`_truncated`, `_total_count`, `_showing`, `_hint`) added to responses so agents know when to adjust
- **Compact summaries** for all list/filter tools — returns only essential fields (id, name, region, account, capacity) by default:
  - `list_all_clusters`, `list_clusters`, `list_clusters_azure`
  - `list_vngs`, `list_vngs_azure`, `list_elastigroups`
  - `list_stateful_nodes`, `list_stateful_nodes_azure`
  - `filter_clusters_by_tag`, `filter_vngs_by_tag`
- `verbose=true` parameter on list/filter tools to opt-in to full configurations
- Progressive disclosure metadata (`_summary`, `_hint`, `_verbose_when`) guides agents on when to request full configs

## [0.4.0] - 2026-03-23

### Added
- **Azure parity improvements** — closing gaps between AWS and Azure tool coverage:
  - **`get_right_sizing`** now supports `cloud="azure"` — uses POST `/ocean/azure/np/cluster/{id}/rightSizing/suggestion`
  - **`list_stateful_nodes_azure`** / **`get_stateful_node_azure`** — Azure Stateful Node support
- **`probe_token_capabilities`** — test which API endpoints your token can access before using tools
- Graceful **401/403 error handling** — clear error messages instead of generic HTTP errors on all API calls
- Azure Stateful Nodes added to capability probe
- 6 new tests (70 total)

### Notes
- Azure does **not** have a detach instances API — `replace` and `remove_permanently` strategies remain AWS-only
- Azure does **not** have an allowed instance types endpoint — VM sizes are configured in VNG settings

## [0.3.0] - 2026-03-23

### Added
- **HTTP/SSE transport** — run as a remote server with `--transport sse` or `--transport streamable-http`
  - Accepts `--host` and `--port` flags
  - Dockerfile defaults to `streamable-http` on port 8000
- 29 new tests (57 total) covering error handling, Azure paths, write operations, tag filtering, YAML export, and more

## [0.2.0] - 2026-03-23

### Added
- **`remove_instances`** — Intent-based instance removal with 3 strategies:
  - `drain_and_replace`: Graceful drain via rolling restart (safest, default)
  - `replace`: Immediate terminate, Ocean auto-replaces (AWS only)
  - `remove_permanently`: Terminate + reduce capacity, no replacement (AWS only)
  - Shows full execution plan before `confirm=true`
- **`get_cluster_health`** — Composite health check: node status, recent errors, active rolls
- **`get_cost_trending`** — Week-over-week (or custom period) cost comparison
- **`get_savings_summary`** — 30-day cost and savings summary
- **`get_cluster_scheduling`** — Scheduling and auto-scaler configuration
- **`list_stateful_nodes`** / **`get_stateful_node`** — AWS Managed Instances support
- **`filter_clusters_by_tag`** / **`filter_vngs_by_tag`** — Tag-based filtering for clusters and VNGs
- **`export_cluster_yaml`** / **`export_vng_yaml`** — Export configs as YAML for GitOps/backup
- Dockerfile for containerized deployment
- `pyyaml` dependency for YAML export

### Fixed
- Cost trending uses sequential API calls (Spot.io returns 400 on concurrent cost requests)
- Mypy type stubs for PyYAML (`types-PyYAML`)

## [0.1.0] - 2026-03-20

### Added
- Initial release with 23 tools (19 read + 4 write)
- **Cross-account**: `list_accounts`, `list_all_clusters` (scans all accounts and clouds)
- **AWS Ocean**: `list_clusters`, `get_cluster`, `list_vngs`, `get_vng`, `list_elastigroups`, `get_elastigroup`, `get_allowed_instance_types`, `get_right_sizing`
- **Azure Ocean**: `list_clusters_azure`, `get_cluster_azure`, `list_vngs_azure`, `get_vng_azure`
- **Both clouds**: `get_cluster_nodes`, `get_cluster_costs`, `list_rolls`, `get_roll`, `get_cluster_log`
- **Write operations** (require `confirm=true`): `initiate_roll`, `detach_instances`, `update_vng`, `update_vng_azure`
- Multi-account support via optional `account_id` parameter on all tools
- CI with GitHub Actions (Python 3.10-3.13, ruff, mypy, pytest)
- PyPI publishing via trusted publishers (OIDC)
- MIT license
