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


# --- Ocean Clusters ---


@mcp.tool()
async def list_clusters(account_id: str = "") -> str:
    """List all Ocean Kubernetes clusters in a Spotinst account.

    Args:
        account_id: Optional account ID to query (e.g. act-be5e7ffe). Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().list_clusters(account_id)
    return _format(result)


@mcp.tool()
async def get_cluster(cluster_id: str, account_id: str = "") -> str:
    """Get details of a specific Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_cluster(cluster_id, account_id)
    return _format(result)


# --- Ocean VNGs (Launch Specs) ---


@mcp.tool()
async def list_vngs(ocean_id: str = "", account_id: str = "") -> str:
    """List Ocean Virtual Node Groups (VNGs / launch specs).

    Args:
        ocean_id: Optional Ocean cluster ID to filter by (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().list_vngs(ocean_id or None, account_id)
    return _format(result)


@mcp.tool()
async def get_vng(vng_id: str, account_id: str = "") -> str:
    """Get details of a specific VNG (launch spec).

    Args:
        vng_id: The VNG/launch spec ID (e.g. ols-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_vng(vng_id, account_id)
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
async def get_cluster_nodes(cluster_id: str, account_id: str = "") -> str:
    """List all nodes in an Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_cluster_nodes(cluster_id, account_id)
    return _format(result)


# --- Ocean Costs ---


@mcp.tool()
async def get_cluster_costs(
    cluster_id: str,
    start_time: str,
    end_time: str,
    group_by: str = "namespace",
    account_id: str = "",
) -> str:
    """Get aggregated cost breakdown for an Ocean cluster over a date range.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        start_time: Start time in ISO 8601 format (e.g. 2026-03-01T00:00:00Z)
        end_time: End time in ISO 8601 format (e.g. 2026-03-20T00:00:00Z)
        group_by: Group costs by: namespace or resource (default: namespace)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_cluster_costs(
        cluster_id, start_time, end_time, group_by, account_id
    )
    return _format(result)


# --- Ocean Right-Sizing ---


@mcp.tool()
async def get_right_sizing(
    cluster_id: str, namespace: str = "", account_id: str = ""
) -> str:
    """Get right-sizing resource suggestions for workloads in an Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        namespace: Optional namespace to filter suggestions
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_right_sizing(cluster_id, namespace, account_id)
    return _format(result)


# --- Ocean Rolls ---


@mcp.tool()
async def list_rolls(cluster_id: str, account_id: str = "") -> str:
    """List all deployment rolls for an Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().list_rolls(cluster_id, account_id)
    return _format(result)


@mcp.tool()
async def get_roll(cluster_id: str, roll_id: str, account_id: str = "") -> str:
    """Get details of a specific Ocean cluster roll.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        roll_id: The roll ID (e.g. scr-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_roll(cluster_id, roll_id, account_id)
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
) -> str:
    """Get scaling and activity log events for an Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        from_date: Start date in YYYY-MM-DD format (e.g. 2026-03-19)
        to_date: End date in YYYY-MM-DD format (e.g. 2026-03-20)
        severity: Filter by severity: ALL, INFO, WARN, ERROR (default: ALL)
        limit: Max number of log entries (default: 500)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_cluster_log(
        cluster_id, from_date, to_date, severity, limit, account_id
    )
    return _format(result)


# --- Allowed Instance Types ---


@mcp.tool()
async def get_allowed_instance_types(
    cluster_id: str, account_id: str = ""
) -> str:
    """Get the list of allowed EC2 instance types for an Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        account_id: Optional account ID to query. Defaults to SPOTINST_ACCOUNT_ID env var.
    """
    result = await _get_client().get_allowed_instance_types(cluster_id, account_id)
    return _format(result)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
