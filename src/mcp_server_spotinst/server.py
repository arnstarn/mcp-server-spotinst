"""MCP server for Spot.io (Spotinst) API."""

import json

from mcp.server.fastmcp import FastMCP

from .spotinst_client import SpotinstClient

mcp = FastMCP("spotinst")
_client: SpotinstClient | None = None


def _get_client() -> SpotinstClient:
    global _client
    if _client is None:
        _client = SpotinstClient()
    return _client


def _format(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


# --- Accounts ---


@mcp.tool()
async def list_accounts() -> str:
    """List all Spotinst accounts accessible with the current token."""
    result = await _get_client().list_accounts()
    return _format(result)


# --- All Clusters (cross-account, cross-cloud) ---


@mcp.tool()
async def list_all_clusters() -> str:
    """List ALL Ocean clusters across ALL accounts and cloud providers (AWS + Azure).
    Scans every account in parallel and returns a unified list with account and cloud info.
    """
    clusters = await _get_client().list_all_clusters()
    return _format(clusters)


# --- Ocean Clusters (AWS) ---


@mcp.tool()
async def list_clusters(account_id: str = "") -> str:
    """List AWS Ocean Kubernetes clusters in a Spotinst account.

    Args:
        account_id: Optional account ID to query (e.g. act-be5e7ffe). Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().list_clusters(account_id)
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
async def list_clusters_azure(account_id: str = "") -> str:
    """List Azure Ocean clusters in a Spotinst account.

    Args:
        account_id: Account ID for an Azure account (e.g. act-9785011e).
    """
    result = await _get_client().list_clusters_azure(account_id)
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
async def list_vngs(ocean_id: str = "", account_id: str = "") -> str:
    """List AWS Ocean Virtual Node Groups (VNGs / launch specs).

    Args:
        ocean_id: Optional Ocean cluster ID to filter by (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().list_vngs(ocean_id or None, account_id)
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
async def list_vngs_azure(ocean_id: str = "", account_id: str = "") -> str:
    """List Azure Ocean Virtual Node Groups.

    Args:
        ocean_id: Optional Ocean cluster ID to filter by (e.g. o-390ef886)
        account_id: Account ID for an Azure account.
    """
    result = await _get_client().list_vngs_azure(ocean_id or None, account_id)
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
async def list_elastigroups(account_id: str = "") -> str:
    """List all Elastigroups in a Spotinst account.

    Args:
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().list_elastigroups(account_id)
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
    cluster_id: str, account_id: str = "", cloud: str = "aws"
) -> str:
    """List all nodes in an Ocean cluster (AWS or Azure).

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_cluster_nodes(cluster_id, account_id, cloud)
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
) -> str:
    """Get aggregated cost breakdown for an Ocean cluster (AWS or Azure).

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        start_time: Start time in ISO 8601 format (e.g. 2026-03-01T00:00:00Z)
        end_time: End time in ISO 8601 format (e.g. 2026-03-20T00:00:00Z)
        group_by: Group costs by: namespace or resource (default: namespace)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
        cloud: Cloud provider: aws or azure (default: aws)
    """
    result = await _get_client().get_cluster_costs(
        cluster_id, start_time, end_time, group_by, account_id, cloud
    )
    return _format(result)


# --- Ocean Right-Sizing (AWS only) ---


@mcp.tool()
async def get_right_sizing(
    cluster_id: str, namespace: str = "", account_id: str = ""
) -> str:
    """Get right-sizing resource suggestions for workloads in an AWS Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        namespace: Optional namespace to filter suggestions
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_right_sizing(cluster_id, namespace, account_id)
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


# ===================================================================
# WRITE OPERATIONS (destructive — require confirm=true)
# ===================================================================


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
) -> str:
    """DESTRUCTIVE: Update an AWS VNG (launch spec) configuration.
    Requires confirm=true. Pass updates as a JSON string.

    Args:
        vng_id: The VNG/launch spec ID (e.g. ols-abc12345)
        updates_json: JSON string of fields to update (e.g. '{"resourceLimits": {"maxInstanceCount": 20}}')
        confirm: Must be true to execute. Safety guard.
        account_id: Optional account ID. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    try:
        updates = json.loads(updates_json)
    except json.JSONDecodeError as e:
        return f"ERROR: Invalid JSON in updates_json: {e}"
    if not confirm:
        return (
            f"SAFETY: Update NOT applied. Set confirm=true to execute.\n"
            f"This will update VNG {vng_id} with: {json.dumps(updates, indent=2)}"
        )
    result = await _get_client().update_vng(vng_id, updates, account_id)
    return _format(result)


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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
