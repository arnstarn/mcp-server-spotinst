"""Tests for the MCP server tool registration and safety guards."""

import pytest

from mcp_server_spotinst.server import mcp, remove_instances


def test_all_tools_registered():
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert len(tools) == 34  # 29 read + 5 write
    assert "list_all_clusters" in tools
    assert "list_clusters_azure" in tools
    assert "initiate_roll" in tools
    assert "detach_instances" in tools
    assert "update_vng" in tools
    assert "update_vng_azure" in tools


def test_write_tools_have_confirm_param():
    """All write tools must have a confirm parameter."""
    write_tools = ["remove_instances", "initiate_roll", "detach_instances", "update_vng", "update_vng_azure"]
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    for name in write_tools:
        assert name in tools, f"Missing write tool: {name}"
        # Get the parameters from the tool's function signature
        params = tools[name].parameters
        props = params.get("properties", {})
        assert "confirm" in props, (
            f"Write tool {name} missing confirm parameter"
        )


def test_write_tool_descriptions_warn():
    """All write tools must have DESTRUCTIVE in their description."""
    write_tools = ["remove_instances", "initiate_roll", "detach_instances", "update_vng", "update_vng_azure"]
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    for name in write_tools:
        desc = tools[name].description or ""
        assert "DESTRUCTIVE" in desc, (
            f"Write tool {name} missing DESTRUCTIVE warning in description"
        )


@pytest.mark.asyncio
async def test_remove_instances_safety_guard():
    """remove_instances must explain the plan when confirm=false."""
    result = await remove_instances("o-abc123", "i-abc,i-def", strategy="drain_and_replace", confirm=False)
    assert "SAFETY" in result
    assert "NOT executed" in result
    assert "DRAIN AND REPLACE" in result
    assert "i-abc" in result
    assert "gracefully drained" in result.lower()


@pytest.mark.asyncio
async def test_remove_instances_invalid_strategy():
    """remove_instances must reject invalid strategies."""
    result = await remove_instances("o-abc123", "i-abc", strategy="yolo")
    assert "ERROR" in result
    assert "Invalid strategy" in result


@pytest.mark.asyncio
async def test_remove_instances_replace_plan():
    """remove_instances 'replace' shows immediate termination plan."""
    result = await remove_instances("o-abc123", "i-abc", strategy="replace", confirm=False)
    assert "REPLACE" in result
    assert "WITHOUT graceful drain" in result


@pytest.mark.asyncio
async def test_remove_instances_remove_permanently_plan():
    """remove_instances 'remove_permanently' warns about no replacement."""
    result = await remove_instances("o-abc123", "i-abc", strategy="remove_permanently", confirm=False)
    assert "PERMANENTLY REMOVE" in result
    assert "no replacements" in result.lower() or "NOT replaced" in result


@pytest.mark.asyncio
async def test_remove_instances_azure_replace_blocked():
    """replace and remove_permanently strategies should be blocked for Azure."""
    result = await remove_instances("o-az1", "vm-abc", strategy="replace", cloud="azure")
    assert "ERROR" in result
    assert "AWS" in result


@pytest.mark.asyncio
async def test_remove_instances_no_ids():
    """remove_instances must error if no instance IDs provided."""
    result = await remove_instances("o-abc123", "", strategy="replace")
    assert "ERROR" in result
    assert "No instance IDs" in result
