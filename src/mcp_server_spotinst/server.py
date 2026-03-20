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


# --- Ocean Clusters ---


@mcp.tool()
async def list_clusters() -> str:
    """List all Ocean Kubernetes clusters in the Spotinst account."""
    result = await _get_client().list_clusters()
    return _format(result)


@mcp.tool()
async def get_cluster(cluster_id: str) -> str:
    """Get details of a specific Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
    """
    result = await _get_client().get_cluster(cluster_id)
    return _format(result)


# --- Ocean VNGs (Launch Specs) ---


@mcp.tool()
async def list_vngs(ocean_id: str = "") -> str:
    """List Ocean Virtual Node Groups (VNGs / launch specs).

    Args:
        ocean_id: Optional Ocean cluster ID to filter by (e.g. o-abc12345)
    """
    result = await _get_client().list_vngs(ocean_id or None)
    return _format(result)


@mcp.tool()
async def get_vng(vng_id: str) -> str:
    """Get details of a specific VNG (launch spec).

    Args:
        vng_id: The VNG/launch spec ID (e.g. ols-abc12345)
    """
    result = await _get_client().get_vng(vng_id)
    return _format(result)


# --- Elastigroups ---


@mcp.tool()
async def list_elastigroups() -> str:
    """List all Elastigroups in the Spotinst account."""
    result = await _get_client().list_elastigroups()
    return _format(result)


@mcp.tool()
async def get_elastigroup(group_id: str) -> str:
    """Get details of a specific Elastigroup.

    Args:
        group_id: The Elastigroup ID (e.g. sig-abc12345)
    """
    result = await _get_client().get_elastigroup(group_id)
    return _format(result)


# --- Ocean Nodes ---


@mcp.tool()
async def get_cluster_nodes(cluster_id: str) -> str:
    """List all nodes in an Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
    """
    result = await _get_client().get_cluster_nodes(cluster_id)
    return _format(result)


# --- Ocean Costs ---


@mcp.tool()
async def get_cluster_costs(
    cluster_id: str, start_time: str, end_time: str, group_by: str = "namespace"
) -> str:
    """Get aggregated cost breakdown for an Ocean cluster over a date range.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        start_time: Start time in ISO 8601 format (e.g. 2026-03-01T00:00:00Z)
        end_time: End time in ISO 8601 format (e.g. 2026-03-20T00:00:00Z)
        group_by: Group costs by: namespace or resource (default: namespace)
    """
    result = await _get_client().get_cluster_costs(
        cluster_id, start_time, end_time, group_by
    )
    return _format(result)


# --- Ocean Right-Sizing ---


@mcp.tool()
async def get_right_sizing(cluster_id: str, namespace: str = "") -> str:
    """Get right-sizing resource suggestions for workloads in an Ocean cluster.

    Args:
        cluster_id: The Ocean cluster ID (e.g. o-abc12345)
        namespace: Optional namespace to filter suggestions
    """
    result = await _get_client().get_right_sizing(cluster_id, namespace)
    return _format(result)


# --- Accounts ---


@mcp.tool()
async def list_accounts() -> str:
    """List all Spotinst accounts accessible with the current token."""
    result = await _get_client().list_accounts()
    return _format(result)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
