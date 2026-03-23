# Changelog

All notable changes to this project will be documented in this file.

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
