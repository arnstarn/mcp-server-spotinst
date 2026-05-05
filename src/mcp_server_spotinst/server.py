"""MCP server for Spot.io (Spotinst) API."""

import base64
import json

import yaml
from mcp.server.fastmcp import FastMCP

from .spotinst_client import SpotinstClient


def _looks_like_base64(s: str) -> bool:
    """Best-effort check that a string is already base64-encoded."""
    if not s:
        return True
    try:
        decoded = base64.b64decode(s, validate=True)
        # If decode succeeds AND the decoded bytes look like text, assume it's base64.
        # An arbitrary shell script would NOT successfully validate as base64.
        decoded.decode("utf-8", errors="strict")
        return True
    except Exception:
        return False


def _extract_launchspec(readback: object) -> dict | None:
    """Pull the first launchSpec item out of a get_vng readback, tolerating shape variants."""
    if not isinstance(readback, dict):
        return None
    items = readback.get("items")
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    # Some code paths return the raw response with `response.items` still nested.
    response = readback.get("response")
    if isinstance(response, dict):
        inner = response.get("items")
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return inner[0]
    return None


def _diff_submitted_vs_readback(
    submitted: dict, readback: object
) -> dict[str, dict]:
    """Return a shallow field-level diff {field: {sent, observed}} for fields in
    `submitted` whose value did not round-trip to `readback`. Empty dict means
    everything we asked for landed.

    `userData` is compared on decoded-plaintext bytes so we don't flag when the
    server re-encodes the same content with different whitespace/padding.
    """
    observed = _extract_launchspec(readback)
    if observed is None:
        return {}
    mismatches: dict[str, dict] = {}
    for key, sent in submitted.items():
        if key not in observed:
            mismatches[key] = {"sent": sent, "observed": None}
            continue
        got = observed[key]
        if key == "userData" and isinstance(sent, str) and isinstance(got, str):
            try:
                sent_bytes = base64.b64decode(sent, validate=True)
            except Exception:
                sent_bytes = sent.encode("utf-8")
            try:
                got_bytes = base64.b64decode(got, validate=True)
            except Exception:
                got_bytes = got.encode("utf-8")
            if sent_bytes != got_bytes:
                mismatches[key] = {
                    "sent_bytes": len(sent_bytes),
                    "observed_bytes": len(got_bytes),
                    "note": "userData did not round-trip; server may have silently dropped the update",
                }
            continue
        if sent != got:
            mismatches[key] = {"sent": sent, "observed": got}
    return mismatches


mcp = FastMCP("spotinst")
_client: SpotinstClient | None = None


def _get_client() -> SpotinstClient:
    global _client
    if _client is None:
        _client = SpotinstClient()
    return _client


def _format(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


def _truncate_items(data: dict, limit: int, sort_key=None, hint: str = "") -> dict:
    """Truncate response items with metadata. limit=0 means no truncation."""
    items = data.get("items", [])
    if limit <= 0 or len(items) <= limit:
        return data
    if sort_key:
        items = sorted(items, key=sort_key, reverse=True)
    return {
        **{k: v for k, v in data.items() if k != "items"},
        "items": items[:limit],
        "_truncated": True,
        "_total_count": len(items),
        "_showing": limit,
        "_hint": hint or "Set limit=0 for all results.",
    }


_CLUSTER_SUMMARY_KEYS = ("id", "name", "controllerClusterId", "region", "state")
_VNG_SUMMARY_KEYS = ("id", "name", "oceanId", "state")
_ELASTIGROUP_SUMMARY_KEYS = ("id", "name", "region", "state")
_STATEFUL_NODE_SUMMARY_KEYS = ("id", "name", "region", "state")


def _summarize(item: dict, keys: tuple) -> dict:
    """Extract summary fields from a resource for compact list responses."""
    summary = {k: item[k] for k in keys if k in item}
    if "aks" in item:
        aks = item["aks"]
        for k in ("name", "resourceGroupName"):
            if k in aks:
                summary[k] = aks[k]
    summary.update({k: v for k, v in item.items() if k.startswith("_")})
    if "capacity" in item:
        summary["capacity"] = item["capacity"]
    return summary


def _with_summary_meta(items: list, resource_type: str) -> dict:
    """Wrap summarized list response with progressive disclosure metadata."""
    return {
        "items": items,
        "_summary": True,
        "_hint": f"Showing compact summaries. Set verbose=true for full {resource_type} configs.",
        "_verbose_when": (
            f"Use verbose=true when you need to inspect networking, instance types, "
            f"scaling settings, or troubleshoot {resource_type} configuration."
        ),
    }


def _truncate_costs(data: dict, limit: int) -> dict:
    """Truncate cost namespace aggregations by total cost descending."""
    if limit <= 0:
        return data
    items = data.get("items", [])
    if not items:
        return data
    detail = items[0] if isinstance(items, list) else items
    aggs = detail.get("detailedCosts", {}).get("aggregations", {})
    if not aggs or len(aggs) <= limit:
        return data
    total_count = len(aggs)
    sorted_ns = sorted(aggs.items(), key=lambda kv: kv[1].get("summary", {}).get("total", 0), reverse=True)
    truncated_aggs = dict(sorted_ns[:limit])
    result = json.loads(json.dumps(data, default=str))
    target = result["items"][0] if isinstance(result["items"], list) else result["items"]
    target["detailedCosts"]["aggregations"] = truncated_aggs
    result["_truncated"] = True
    result["_total_count"] = total_count
    result["_showing"] = limit
    result["_hint"] = "Set limit=0 for all namespaces, or use namespace param to filter."
    return result


# --- Token Capabilities ---


@mcp.tool()
async def probe_token_capabilities() -> str:
    """Probe which Spot.io API endpoints the current token can access.
    Call this first to understand what tools will work with your token.
    Returns a report of accessible vs denied endpoints.
    """
    result = await _get_client().probe_capabilities()
    return _format(result)


# --- Accounts ---


@mcp.tool()
async def list_accounts() -> str:
    """List all Spotinst accounts accessible with the current token."""
    result = await _get_client().list_accounts()
    return _format(result)


# --- All Clusters (cross-account, cross-cloud) ---


@mcp.tool()
async def list_all_clusters(verbose: bool = False) -> str:
    """List ALL Ocean clusters across ALL accounts and cloud providers (AWS + Azure).
    Scans every account in parallel and returns a unified list with account and cloud info.
    Returns compact summaries by default (id, name, region, account, capacity).
    Set verbose=true for full cluster configs (networking, instance types, autoscaler).

    Args:
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing cluster settings, troubleshooting, or comparing configs.
    """
    clusters = await _get_client().list_all_clusters()
    if not verbose:
        items = [_summarize(c, _CLUSTER_SUMMARY_KEYS) for c in clusters]
        return _format(_with_summary_meta(items, "cluster"))
    return _format(clusters)


# --- Ocean Clusters (AWS) ---


@mcp.tool()
async def list_clusters(account_id: str = "", verbose: bool = False) -> str:
    """List AWS Ocean Kubernetes clusters in a Spotinst account.
    Returns compact summaries by default (id, name, region, capacity).
    Set verbose=true for full cluster configs (networking, instance types, autoscaler).

    Args:
        account_id: Optional account ID to query (e.g. act-be5e7ffe). Defaults to SPOTINST_ACCOUNT_ID env var.
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing cluster settings, troubleshooting, or comparing configs.
    """
    result = await _get_client().list_clusters(account_id)
    if not verbose:
        items = [_summarize(c, _CLUSTER_SUMMARY_KEYS) for c in result.get("items", [])]
        return _format(_with_summary_meta(items, "cluster"))
    return _format(result)


@mcp.tool()
async def get_cluster(cluster_id: str, account_id: str = "") -> str:
    """Get details of a specific AWS Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_cluster(cluster_id, account_id)
    return _format(result)


# --- Ocean Clusters (Azure) ---


@mcp.tool()
async def list_clusters_azure(account_id: str = "", verbose: bool = False) -> str:
    """List Azure Ocean clusters in a Spotinst account.
    Returns compact summaries by default (id, name, capacity).
    Set verbose=true for full cluster configs (networking, VM sizes, autoscaler).

    Args:
        account_id: Account ID for an Azure account (e.g. act-9785011e).
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing cluster settings, troubleshooting, or comparing configs.
    """
    result = await _get_client().list_clusters_azure(account_id)
    if not verbose:
        items = [_summarize(c, _CLUSTER_SUMMARY_KEYS) for c in result.get("items", [])]
        return _format(_with_summary_meta(items, "cluster"))
    return _format(result)


@mcp.tool()
async def get_cluster_azure(cluster_id: str, account_id: str = "") -> str:
    """Get details of a specific Azure Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-390ef886)
        account_id: Account ID for an Azure account.
    """
    result = await _get_client().get_cluster_azure(cluster_id, account_id)
    return _format(result)


# --- Ocean VNGs (AWS) ---


@mcp.tool()
async def list_vngs(ocean_id: str = "", account_id: str = "", verbose: bool = False) -> str:
    """List AWS Ocean Virtual Node Groups (VNGs / launch specs).
    Returns compact summaries by default (id, name, oceanId).
    Set verbose=true for full VNG configs (AMI, subnets, resource limits, labels).

    Args:
        ocean_id: Optional Ocean cluster ID to filter by (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing VNG settings, troubleshooting, or comparing configs.
    """
    result = await _get_client().list_vngs(ocean_id or None, account_id)
    if not verbose:
        items = [_summarize(c, _VNG_SUMMARY_KEYS) for c in result.get("items", [])]
        return _format(_with_summary_meta(items, "VNG"))
    return _format(result)


@mcp.tool()
async def get_vng(vng_id: str, account_id: str = "") -> str:
    """Get details of a specific AWS VNG (launch spec).

    Args:
        vng_id: The VNG/launch spec ID (e.g. ols-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_vng(vng_id, account_id)
    return _format(result)


# --- Ocean VNGs (Azure) ---


@mcp.tool()
async def list_vngs_azure(ocean_id: str = "", account_id: str = "", verbose: bool = False) -> str:
    """List Azure Ocean Virtual Node Groups.
    Returns compact summaries by default (id, name, oceanId).
    Set verbose=true for full VNG configs (VM sizes, labels, resource limits).

    Args:
        ocean_id: Optional Ocean cluster ID to filter by (e.g. o-390ef886)
        account_id: Account ID for an Azure account.
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing VNG settings, troubleshooting, or comparing configs.
    """
    result = await _get_client().list_vngs_azure(ocean_id or None, account_id)
    if not verbose:
        items = [_summarize(c, _VNG_SUMMARY_KEYS) for c in result.get("items", [])]
        return _format(_with_summary_meta(items, "VNG"))
    return _format(result)


@mcp.tool()
async def get_vng_azure(vng_id: str, account_id: str = "") -> str:
    """Get details of a specific Azure VNG.

    Args:
        vng_id: The VNG ID (e.g. vng-14e08b61)
        account_id: Account ID for an Azure account.
    """
    result = await _get_client().get_vng_azure(vng_id, account_id)
    return _format(result)


# --- Elastigroups ---


@mcp.tool()
async def list_elastigroups(account_id: str = "", verbose: bool = False) -> str:
    """List all Elastigroups in a Spotinst account.
    Returns compact summaries by default (id, name, region, capacity).
    Set verbose=true for full Elastigroup configs (compute, networking, scaling).

    Args:
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing Elastigroup settings, troubleshooting, or comparing configs.
    """
    result = await _get_client().list_elastigroups(account_id)
    if not verbose:
        items = [_summarize(c, _ELASTIGROUP_SUMMARY_KEYS) for c in result.get("items", [])]
        return _format(_with_summary_meta(items, "Elastigroup"))
    return _format(result)


@mcp.tool()
async def get_elastigroup(group_id: str, account_id: str = "") -> str:
    """Get details of a specific Elastigroup.

    Args:
        group_id: The Elastigroup ID (e.g. sig-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_elastigroup(group_id, account_id)
    return _format(result)


# --- Ocean Nodes ---


@mcp.tool()
async def get_cluster_nodes(
    cluster_id: str, account_id: str = "", cloud: str = "aws", limit: int = 50
) -> str:
    """List all nodes in an Ocean cluster (AWS or Azure).

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
        limit: Max items to return (default: 50). Set limit=0 for all results.
    """
    result = await _get_client().get_cluster_nodes(cluster_id, account_id, cloud)
    result = _truncate_items(result, limit, hint="Set limit=0 for all results.")
    return _format(result)


# --- Ocean Costs ---


@mcp.tool()
async def get_cluster_costs(
    cluster_id: str,
    start_time: str,
    end_time: str,
    group_by: str = "namespace",
    account_id: str = "",
    cloud: str = "aws",
    limit: int = 50,
) -> str:
    """Get aggregated cost breakdown for an Ocean cluster (AWS or Azure).

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        start_time: Start time in ISO 8601 format (e.g. 2026-03-01T00:00:00Z)
        end_time: End time in ISO 8601 format (e.g. 2026-03-20T00:00:00Z)
        group_by: Group costs by: namespace (default: namespace). Only 'namespace' is currently supported by the API.
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
        limit: Max namespace aggregations to return, sorted by cost descending (default: 50). Set limit=0 for all.
    """
    result = await _get_client().get_cluster_costs(
        cluster_id, start_time, end_time, group_by, account_id, cloud
    )
    # Truncate namespace aggregations by cost
    result = _truncate_costs(result, limit)
    return _format(result)


# --- Ocean Right-Sizing ---


@mcp.tool()
async def get_right_sizing(
    cluster_id: str, namespace: str = "", account_id: str = "", cloud: str = "aws", limit: int = 50
) -> str:
    """Get right-sizing resource suggestions for workloads in an Ocean cluster (AWS or Azure).
    Results are sorted by savings potential (biggest CPU delta first) and truncated to `limit`.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        namespace: Optional namespace to filter suggestions
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
        limit: Max items to return, sorted by savings potential (default: 50). Set limit=0 for all results.
    """
    client = _get_client()
    if cloud == "azure":
        result = await client.get_right_sizing_azure(cluster_id, namespace, account_id)
    else:
        result = await client.get_right_sizing(cluster_id, namespace, account_id)

    def _cpu_delta(item: dict) -> float:
        requested = item.get("requestedCPU", 0) or item.get("requestedCpu", 0) or 0
        suggested = item.get("suggestedCPU", 0) or item.get("suggestedCpu", 0) or 0
        return float(requested) - float(suggested)

    result = _truncate_items(
        result, limit, sort_key=_cpu_delta,
        hint="Set limit=0 for all results, or use namespace param to filter.",
    )
    return _format(result)


# --- Ocean Rolls ---


@mcp.tool()
async def list_rolls(
    cluster_id: str, account_id: str = "", cloud: str = "aws"
) -> str:
    """List all deployment rolls for an Ocean cluster (AWS or Azure).

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().list_rolls(cluster_id, account_id, cloud)
    return _format(result)


@mcp.tool()
async def get_roll(
    cluster_id: str, roll_id: str, account_id: str = "", cloud: str = "aws"
) -> str:
    """Get details of a specific Ocean cluster roll (AWS or Azure).

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        roll_id: The roll ID (e.g. scr-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_roll(cluster_id, roll_id, account_id, cloud)
    return _format(result)


# --- Ocean Cluster Log ---


@mcp.tool()
async def get_cluster_log(
    cluster_id: str,
    from_date: str,
    to_date: str,
    severity: str = "ALL",
    limit: int = 500,
    account_id: str = "",
    cloud: str = "aws",
) -> str:
    """Get scaling and activity log events for an Ocean cluster (AWS or Azure).

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        from_date: Start date in YYYY-MM-DD format (e.g. 2026-03-19)
        to_date: End date in YYYY-MM-DD format (e.g. 2026-03-20)
        severity: Filter by severity: ALL, INFO, WARN, ERROR (default: ALL)
        limit: Max number of log entries (default: 500)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_cluster_log(
        cluster_id, from_date, to_date, severity, limit, account_id, cloud
    )
    return _format(result)


# --- Allowed Instance Types (AWS only) ---


@mcp.tool()
async def get_allowed_instance_types(
    cluster_id: str, account_id: str = ""
) -> str:
    """Get the list of allowed EC2 instance types for an AWS Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_allowed_instance_types(cluster_id, account_id)
    return _format(result)


# --- Stateful Nodes (AWS Managed Instances) ---


@mcp.tool()
async def list_stateful_nodes(account_id: str = "", verbose: bool = False) -> str:
    """List all Stateful Nodes (Managed Instances) in an AWS account.
    Returns compact summaries by default (id, name, region, capacity).
    Set verbose=true for full configs (compute, networking, persistence).

    Args:
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing node settings, troubleshooting, or comparing configs.
    """
    result = await _get_client().list_stateful_nodes(account_id)
    if not verbose:
        items = [_summarize(c, _STATEFUL_NODE_SUMMARY_KEYS) for c in result.get("items", [])]
        return _format(_with_summary_meta(items, "stateful node"))
    return _format(result)


@mcp.tool()
async def get_stateful_node(node_id: str, account_id: str = "") -> str:
    """Get details of a specific AWS Stateful Node (Managed Instance).

    Args:
        node_id: The Managed Instance ID (e.g. smi-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_stateful_node(node_id, account_id)
    return _format(result)


# --- Stateful Nodes (Azure) ---


@mcp.tool()
async def list_stateful_nodes_azure(account_id: str = "", verbose: bool = False) -> str:
    """List all Azure Stateful Nodes in an account.
    Returns compact summaries by default (id, name, capacity).
    Set verbose=true for full configs (compute, networking, persistence).

    Args:
        account_id: Account ID for an Azure account.
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing node settings, troubleshooting, or comparing configs.
    """
    result = await _get_client().list_stateful_nodes_azure(account_id)
    if not verbose:
        items = [_summarize(c, _STATEFUL_NODE_SUMMARY_KEYS) for c in result.get("items", [])]
        return _format(_with_summary_meta(items, "stateful node"))
    return _format(result)


@mcp.tool()
async def get_stateful_node_azure(node_id: str, account_id: str = "") -> str:
    """Get details of a specific Azure Stateful Node.

    Args:
        node_id: The Azure Stateful Node ID
        account_id: Account ID for an Azure account.
    """
    result = await _get_client().get_stateful_node_azure(node_id, account_id)
    return _format(result)


# --- Scheduling ---


@mcp.tool()
async def get_cluster_scheduling(cluster_id: str, account_id: str = "", cloud: str = "aws") -> str:
    """Get scheduling and auto-scaler configuration for an Ocean cluster (AWS or Azure).
    Shows shutdown hours, scheduled tasks, and auto-scaler settings.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_cluster_scheduling(cluster_id, account_id, cloud)
    # Extract just the scheduling-relevant fields
    items = result.get("items", [])
    if items:
        cluster = items[0]
        scheduling_info = {
            "scheduling": cluster.get("scheduling", {}),
            "autoScaler": cluster.get("autoScaler", {}),
        }
        return _format(scheduling_info)
    return _format(result)


# --- Cluster Health Check ---


@mcp.tool()
async def get_cluster_health(cluster_id: str, account_id: str = "", cloud: str = "aws") -> str:
    """Composite health check for an Ocean cluster. Returns node status, recent errors, and active rolls in one call.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_cluster_health(cluster_id, account_id, cloud)
    return _format(result)


# --- Cost Trending ---


@mcp.tool()
async def get_cost_trending(
    cluster_id: str,
    periods: int = 4,
    period_days: int = 7,
    group_by: str = "namespace",
    account_id: str = "",
    cloud: str = "aws",
) -> str:
    """Get cost trends over multiple time periods for an Ocean cluster.

    Shows week-over-week or custom period cost changes.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        periods: Number of time periods to compare (default: 4)
        period_days: Days per period (default: 7 for weekly)
        group_by: Group costs by: namespace (default: namespace). Only 'namespace' is currently supported by the API.
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_cost_trending(cluster_id, periods, period_days, group_by, account_id, cloud)
    return _format(result)


# --- Savings Summary ---


@mcp.tool()
async def get_savings_summary(cluster_id: str, account_id: str = "", cloud: str = "aws") -> str:
    """Get a 30-day cost/savings summary for an Ocean cluster. Shows total spend, spot savings, and cost breakdown.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_cluster_summary(cluster_id, account_id, cloud)
    return _format(result)


# --- Filter by Tags ---


@mcp.tool()
async def filter_clusters_by_tag(
    tag_key: str, tag_value: str = "", account_id: str = "", cloud: str = "aws", verbose: bool = False
) -> str:
    """Filter Ocean clusters by tag key (and optionally tag value). Works for AWS and Azure.
    Returns compact summaries by default. Set verbose=true for full cluster configs.

    Args:
        tag_key: Tag key to filter by (e.g. environment, team)
        tag_value: Optional tag value to match (e.g. production). If empty, matches any value for the key.
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing cluster settings, troubleshooting, or comparing configs.
    """
    client = _get_client()
    if cloud == "azure":
        resp = await client.list_clusters_azure(account_id)
    else:
        resp = await client.list_clusters(account_id)

    clusters = resp.get("items", [])
    matched = []
    for c in clusters:
        tags = c.get("tags", [])
        # Tags can be list of {tagKey, tagValue} or dict
        if isinstance(tags, list):
            for t in tags:
                k = t.get("tagKey", t.get("key", ""))
                v = t.get("tagValue", t.get("value", ""))
                if k == tag_key and (not tag_value or v == tag_value):
                    matched.append(c)
                    break
        elif isinstance(tags, dict) and tag_key in tags:
            if not tag_value or tags[tag_key] == tag_value:
                matched.append(c)
    if not verbose:
        matched = [_summarize(c, _CLUSTER_SUMMARY_KEYS) for c in matched]
    return _format({"matched": len(matched), "clusters": matched})


@mcp.tool()
async def filter_vngs_by_tag(
    tag_key: str, tag_value: str = "", ocean_id: str = "", account_id: str = "", cloud: str = "aws",
    verbose: bool = False,
) -> str:
    """Filter VNGs by tag key (and optionally tag value). Works for AWS and Azure.
    Returns compact summaries by default. Set verbose=true for full VNG configs.

    Args:
        tag_key: Tag key to filter by (e.g. team, workload-type)
        tag_value: Optional tag value to match. If empty, matches any value for the key.
        ocean_id: Optional Ocean cluster ID to filter by
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
        verbose: Return full configurations instead of compact summaries (default: false).
                 Use when analyzing VNG settings, troubleshooting, or comparing configs.
    """
    client = _get_client()
    if cloud == "azure":
        resp = await client.list_vngs_azure(ocean_id or None, account_id)
    else:
        resp = await client.list_vngs(ocean_id or None, account_id)

    vngs = resp.get("items", [])
    matched = []
    for v in vngs:
        tags = v.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                k = t.get("tagKey", t.get("key", ""))
                val = t.get("tagValue", t.get("value", ""))
                if k == tag_key and (not tag_value or val == tag_value):
                    matched.append(v)
                    break
        elif isinstance(tags, dict) and tag_key in tags:
            if not tag_value or tags[tag_key] == tag_value:
                matched.append(v)
    if not verbose:
        matched = [_summarize(v, _VNG_SUMMARY_KEYS) for v in matched]
    return _format({"matched": len(matched), "vngs": matched})


# --- Export to YAML ---


@mcp.tool()
async def export_cluster_yaml(cluster_id: str, account_id: str = "", cloud: str = "aws") -> str:
    """Export an Ocean cluster configuration as YAML. Useful for GitOps comparison or backup.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    client = _get_client()
    if cloud == "azure":
        result = await client.get_cluster_azure(cluster_id, account_id)
    else:
        result = await client.get_cluster(cluster_id, account_id)
    items = result.get("items", [result])
    config = items[0] if items else result
    return yaml.dump(config, default_flow_style=False, sort_keys=False)


@mcp.tool()
async def export_vng_yaml(vng_id: str, account_id: str = "", cloud: str = "aws") -> str:
    """Export a VNG configuration as YAML. Useful for GitOps comparison or backup.

    Args:
        vng_id: The VNG ID (e.g. ols-abc12345 for AWS, vng-abc12345 for Azure)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    client = _get_client()
    if cloud == "azure":
        result = await client.get_vng_azure(vng_id, account_id)
    else:
        result = await client.get_vng(vng_id, account_id)
    items = result.get("items", [result])
    config = items[0] if items else result
    return yaml.dump(config, default_flow_style=False, sort_keys=False)


# ===================================================================
# WRITE OPERATIONS (destructive — require confirm=true)
# ===================================================================


@mcp.tool()
async def remove_instances(
    cluster_id: str,
    instance_ids: str,
    strategy: str = "",
    confirm: bool = False,
    batch_size_percentage: int = 20,
    account_id: str = "",
    cloud: str = "aws",
) -> str:
    """DESTRUCTIVE: Remove instances from an Ocean cluster using a named strategy.
    This is the RECOMMENDED tool for instance removal — it picks the right API call for you.
    Requires confirm=true.

    Strategies:
      - "drain_and_replace": Gracefully drain pods (respects PDBs), terminate, Ocean replaces.
        Uses rolling restart. SAFEST option for production. (Default if not specified)
      - "replace": Immediately terminate instances, Ocean auto-scales replacements.
        Faster but no graceful drain — pods are killed abruptly.
      - "remove_permanently": Terminate instances AND reduce cluster capacity.
        Instances are gone and NOT replaced. Use for downsizing.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        instance_ids: Comma-separated instance IDs (e.g. i-abc123,i-def456)
        strategy: One of: drain_and_replace, replace, remove_permanently
        confirm: Must be true to execute. Safety guard.
        batch_size_percentage: For drain_and_replace only: % of nodes per batch (default: 20)
        account_id: Optional account ID. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws). Note: replace and remove_permanently are AWS-only.
    """
    ids = [s.strip() for s in instance_ids.split(",") if s.strip()]
    if not ids:
        return "ERROR: No instance IDs provided."

    valid_strategies = ("drain_and_replace", "replace", "remove_permanently")
    if not strategy:
        strategy = "drain_and_replace"
    if strategy not in valid_strategies:
        return (
            f"ERROR: Invalid strategy '{strategy}'.\n"
            f"Valid strategies:\n"
            f"  - drain_and_replace: Graceful drain + terminate + Ocean replaces (safest)\n"
            f"  - replace: Terminate immediately + Ocean replaces (no drain)\n"
            f"  - remove_permanently: Terminate + reduce capacity (no replacement)"
        )

    # Build the plan description
    if strategy == "drain_and_replace":
        plan = (
            f"DRAIN AND REPLACE {len(ids)} instance(s) in cluster {cluster_id}:\n"
            f"  Instances: {ids}\n"
            f"  Method: Rolling restart ({batch_size_percentage}% per batch)\n"
            f"  - Pods will be gracefully drained (PDBs respected)\n"
            f"  - Instances will be terminated after drain\n"
            f"  - Ocean will automatically launch replacements"
        )
    elif strategy == "replace":
        if cloud == "azure":
            return "ERROR: 'replace' strategy is only available for AWS clusters. Use 'drain_and_replace' for Azure."
        plan = (
            f"REPLACE {len(ids)} instance(s) in cluster {cluster_id}:\n"
            f"  Instances: {ids}\n"
            f"  Method: Detach + terminate (immediate)\n"
            f"  - Pods will be killed WITHOUT graceful drain\n"
            f"  - Instances will be terminated immediately\n"
            f"  - Ocean will automatically launch replacements"
        )
    else:  # remove_permanently
        if cloud == "azure":
            return "ERROR: 'remove_permanently' strategy is only available for AWS clusters."
        plan = (
            f"PERMANENTLY REMOVE {len(ids)} instance(s) from cluster {cluster_id}:\n"
            f"  Instances: {ids}\n"
            f"  Method: Detach + terminate + reduce capacity\n"
            f"  - Pods will be killed WITHOUT graceful drain\n"
            f"  - Instances will be terminated\n"
            f"  - Cluster capacity will be REDUCED (no replacements)"
        )

    if not confirm:
        return f"SAFETY: Action NOT executed. Set confirm=true to proceed.\n\n{plan}"

    client = _get_client()
    if strategy == "drain_and_replace":
        result = await client.initiate_roll(
            cluster_id,
            batch_size_percentage=batch_size_percentage,
            instance_ids=ids,
            account_id=account_id,
            cloud=cloud,
        )
    elif strategy == "replace":
        result = await client.detach_instances(
            cluster_id,
            instance_ids=ids,
            should_terminate_instances=True,
            should_decrement_target_capacity=False,
            account_id=account_id,
        )
    else:  # remove_permanently
        result = await client.detach_instances(
            cluster_id,
            instance_ids=ids,
            should_terminate_instances=True,
            should_decrement_target_capacity=True,
            account_id=account_id,
        )

    return f"EXECUTED: {strategy}\n\n{plan}\n\nResult:\n{_format(result)}"


@mcp.tool()
async def initiate_roll(
    cluster_id: str,
    confirm: bool = False,
    batch_size_percentage: int = 20,
    batch_min_healthy_percentage: int = 50,
    respect_pdb: bool = True,
    launch_spec_ids: str = "",
    instance_ids: str = "",
    account_id: str = "",
    cloud: str = "aws",
) -> str:
    """DESTRUCTIVE: Initiate a rolling restart of nodes in an Ocean cluster.
    This will drain and replace nodes in batches. Requires confirm=true.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        confirm: Must be true to execute. Safety guard against accidental rolls.
        batch_size_percentage: Percentage of nodes to roll per batch (default: 20)
        batch_min_healthy_percentage: Min healthy nodes per batch (default: 50)
        respect_pdb: Respect PodDisruptionBudgets (default: true)
        launch_spec_ids: Comma-separated VNG IDs to roll (e.g. ols-abc,ols-def). Empty = all.
        instance_ids: Comma-separated instance IDs to roll. Empty = all in scope.
        account_id: Optional account ID. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    if not confirm:
        return (
            "SAFETY: Roll NOT initiated. Set confirm=true to execute.\n"
            f"This will rolling-restart nodes in cluster {cluster_id} "
            f"({batch_size_percentage}% per batch)."
        )
    lspec_ids = [s.strip() for s in launch_spec_ids.split(",") if s.strip()] or None
    inst_ids = [s.strip() for s in instance_ids.split(",") if s.strip()] or None
    result = await _get_client().initiate_roll(
        cluster_id,
        batch_size_percentage,
        batch_min_healthy_percentage,
        respect_pdb,
        lspec_ids,
        inst_ids,
        account_id,
        cloud,
    )
    return _format(result)


@mcp.tool()
async def detach_instances(
    cluster_id: str,
    instance_ids: str,
    confirm: bool = False,
    should_terminate: bool = True,
    should_decrement_capacity: bool = True,
    account_id: str = "",
) -> str:
    """DESTRUCTIVE: Detach and optionally terminate instances from an AWS Ocean cluster.
    Requires confirm=true.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        instance_ids: Comma-separated EC2 instance IDs (e.g. i-abc123,i-def456)
        confirm: Must be true to execute. Safety guard.
        should_terminate: Terminate instances after detach (default: true)
        should_decrement_capacity: Reduce target capacity (default: true)
        account_id: Optional account ID. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    ids = [s.strip() for s in instance_ids.split(",") if s.strip()]
    if not confirm:
        action = "terminate and detach" if should_terminate else "detach (keep running)"
        return (
            f"SAFETY: Detach NOT executed. Set confirm=true to execute.\n"
            f"This will {action} {len(ids)} instance(s) from cluster {cluster_id}: {ids}"
        )
    if not ids:
        return "ERROR: No instance IDs provided."
    result = await _get_client().detach_instances(
        cluster_id, ids, should_decrement_capacity, should_terminate, account_id
    )
    return _format(result)


@mcp.tool()
async def update_vng(
    vng_id: str,
    updates_json: str,
    confirm: bool = False,
    account_id: str = "",
    auto_apply_tags: bool | None = None,
    encode_user_data: bool = True,
) -> str:
    """DESTRUCTIVE: Update an AWS VNG (launch spec) configuration.
    Requires confirm=true. Pass updates as a JSON string.

    The Spot.io API requires `userData` to be **base64-encoded**. This tool
    auto-encodes plaintext userData by default (set encode_user_data=false to
    opt out if you're passing already-encoded data).

    Args:
        vng_id: The VNG/launch spec ID (e.g. ols-abc12345)
        updates_json: JSON string of fields to update (e.g. '{"resourceLimits": {"maxInstanceCount": 20}}')
        confirm: Must be true to execute. Safety guard.
        account_id: Optional account ID. Defaults to SPOTINST_ACCOUNT_ID env var.
        auto_apply_tags: If true, update resource tags without triggering a roll.
                         If None (default), omitted from request (Spot default applies).
        encode_user_data: If true (default) and `userData` is present but not already
                          base64, base64-encode it before sending. Set false to pass
                          through as-is.
    """
    try:
        updates = json.loads(updates_json)
    except json.JSONDecodeError as e:
        return f"ERROR: Invalid JSON in updates_json: {e}"

    if encode_user_data and isinstance(updates.get("userData"), str):
        raw = updates["userData"]
        if not _looks_like_base64(raw):
            updates["userData"] = base64.b64encode(raw.encode("utf-8")).decode("ascii")

    if not confirm:
        preview = dict(updates)
        if isinstance(preview.get("userData"), str) and len(preview["userData"]) > 200:
            preview["userData"] = (
                preview["userData"][:200]
                + f"... [truncated, total {len(preview['userData'])} chars]"
            )
        return (
            f"SAFETY: Update NOT applied. Set confirm=true to execute.\n"
            f"This will update VNG {vng_id} with: {json.dumps(preview, indent=2)}"
        )
    client = _get_client()
    put_result = await client.update_vng(
        vng_id, updates, account_id, auto_apply_tags=auto_apply_tags
    )
    try:
        readback = await client.get_vng(vng_id, account_id)
    except Exception as e:
        readback = {"_readback_error": f"{type(e).__name__}: {e}"}
    payload: dict[str, object] = {"put_result": put_result, "readback": readback}
    mismatches = _diff_submitted_vs_readback(updates, readback)
    if mismatches:
        payload["_readback_mismatch"] = mismatches
        payload["_readback_mismatch_hint"] = (
            "Fields we submitted did not round-trip to the server. Spot.io has "
            "been seen to return 200 OK without persisting the change. Re-apply "
            "or investigate before trusting the update."
        )
    return _format(payload)


@mcp.tool()
async def update_vng_azure(
    vng_id: str,
    updates_json: str,
    confirm: bool = False,
    account_id: str = "",
) -> str:
    """DESTRUCTIVE: Update an Azure VNG configuration.
    Requires confirm=true. Pass updates as a JSON string.

    Args:
        vng_id: The VNG ID (e.g. vng-14e08b61)
        updates_json: JSON string of fields to update
        confirm: Must be true to execute. Safety guard.
        account_id: Account ID for an Azure account.
    """
    try:
        updates = json.loads(updates_json)
    except json.JSONDecodeError as e:
        return f"ERROR: Invalid JSON in updates_json: {e}"
    if not confirm:
        return (
            f"SAFETY: Update NOT applied. Set confirm=true to execute.\n"
            f"This will update Azure VNG {vng_id} with: {json.dumps(updates, indent=2)}"
        )
    result = await _get_client().update_vng_azure(vng_id, updates, account_id)
    return _format(result)


@mcp.tool()
async def create_vng(
    ocean_id: str,
    spec_json: str,
    confirm: bool = False,
    account_id: str = "",
    initial_nodes: int | None = None,
    encode_user_data: bool = True,
) -> str:
    """DESTRUCTIVE: Create a new AWS VNG (launch spec) under an Ocean cluster.
    Requires confirm=true. Pass the launch spec fields as a JSON string.

    `oceanId` is injected from the `ocean_id` argument; don't include it in `spec_json`.
    Like update_vng, plaintext `userData` is auto-encoded to base64 by default.

    Args:
        ocean_id: The parent Ocean cluster ID (e.g. o-abcd1234). Required.
        spec_json: JSON string of launch spec fields (name, instanceTypes, labels, taints,
                   resourceLimits, userData, etc.). Do not include `oceanId`.
        confirm: Must be true to execute. Safety guard.
        account_id: Optional account ID. Defaults to SPOTINST_ACCOUNT_ID env var.
        initial_nodes: If >0, Spot launches that many nodes immediately on create.
        encode_user_data: If true (default) and `userData` is plaintext, base64-encode
                          it before sending.
    """
    try:
        spec = json.loads(spec_json)
    except json.JSONDecodeError as e:
        return f"ERROR: Invalid JSON in spec_json: {e}"

    if "oceanId" in spec:
        return "ERROR: Do not pass oceanId in spec_json; use the ocean_id argument."

    if encode_user_data and isinstance(spec.get("userData"), str):
        raw = spec["userData"]
        if not _looks_like_base64(raw):
            spec["userData"] = base64.b64encode(raw.encode("utf-8")).decode("ascii")

    if not confirm:
        preview = dict(spec)
        if isinstance(preview.get("userData"), str) and len(preview["userData"]) > 200:
            preview["userData"] = (
                preview["userData"][:200]
                + f"... [truncated, total {len(preview['userData'])} chars]"
            )
        return (
            f"SAFETY: Create NOT executed. Set confirm=true to execute.\n"
            f"This will create a VNG under Ocean {ocean_id} "
            f"(initial_nodes={initial_nodes}) with: {json.dumps(preview, indent=2)}"
        )
    result = await _get_client().create_vng(
        ocean_id, spec, account_id=account_id, initial_nodes=initial_nodes
    )
    return _format(result)


@mcp.tool()
async def delete_vng(
    vng_id: str,
    confirm: bool = False,
    account_id: str = "",
    delete_nodes: bool = False,
    force_delete: bool = False,
) -> str:
    """DESTRUCTIVE: Delete an AWS VNG (launch spec).
    Requires confirm=true.

    Args:
        vng_id: The VNG/launch spec ID to delete.
        confirm: Must be true to execute. Safety guard.
        account_id: Optional account ID. Defaults to SPOTINST_ACCOUNT_ID env var.
        delete_nodes: If true, drain + detach + terminate all nodes in this VNG.
                      If false (default), VNG is deleted but nodes continue until
                      they naturally terminate or are moved.
        force_delete: If true, delete even if this is the only non-template VNG.
    """
    if not confirm:
        parts = [f"Delete VNG {vng_id}"]
        if delete_nodes:
            parts.append("AND drain+terminate all its nodes")
        if force_delete:
            parts.append("(force_delete=true)")
        return (
            f"SAFETY: Delete NOT executed. Set confirm=true to execute.\n"
            f"This will {' '.join(parts)}."
        )
    result = await _get_client().delete_vng(
        vng_id,
        account_id=account_id,
        delete_nodes=delete_nodes,
        force_delete=force_delete,
    )
    return _format(result)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="MCP server for Spot.io (Spotinst) API")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind for HTTP transports (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind for HTTP transports (default: 8000)")
    args = parser.parse_args()

    if args.transport in ("sse", "streamable-http"):
        mcp.settings.host = args.host
        mcp.settings.port = args.port

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
