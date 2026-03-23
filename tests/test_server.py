"""Tests for the MCP server tool registration and safety guards."""

from mcp_server_spotinst.server import mcp


def test_all_tools_registered():
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert len(tools) == 33  # 29 read + 4 write
    assert "list_all_clusters" in tools
    assert "list_clusters_azure" in tools
    assert "initiate_roll" in tools
    assert "detach_instances" in tools
    assert "update_vng" in tools
    assert "update_vng_azure" in tools


def test_write_tools_have_confirm_param():
    """All write tools must have a confirm parameter."""
    write_tools = ["initiate_roll", "detach_instances", "update_vng", "update_vng_azure"]
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
    write_tools = ["initiate_roll", "detach_instances", "update_vng", "update_vng_azure"]
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    for name in write_tools:
        desc = tools[name].description or ""
        assert "DESTRUCTIVE" in desc, (
            f"Write tool {name} missing DESTRUCTIVE warning in description"
        )
