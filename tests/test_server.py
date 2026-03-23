"""Tests for the MCP server tool registration and safety guards."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_server_spotinst.server import (
    export_cluster_yaml,
    filter_clusters_by_tag,
    filter_vngs_by_tag,
    get_cluster_scheduling,
    get_right_sizing,
    list_stateful_nodes_azure,
    mcp,
    remove_instances,
)


def test_all_tools_registered():
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert len(tools) == 37  # 32 read + 5 write
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


@pytest.mark.asyncio
async def test_remove_instances_default_strategy():
    """remove_instances defaults to drain_and_replace when no strategy given."""
    result = await remove_instances("o-abc123", "i-abc", confirm=False)
    assert "DRAIN AND REPLACE" in result


@pytest.mark.asyncio
async def test_filter_clusters_by_tag_matches():
    """filter_clusters_by_tag should match clusters with matching tags."""
    mock_resp = {
        "items": [
            {"id": "o-1", "name": "prod", "tags": [{"tagKey": "env", "tagValue": "production"}]},
            {"id": "o-2", "name": "dev", "tags": [{"tagKey": "env", "tagValue": "development"}]},
            {"id": "o-3", "name": "staging", "tags": []},
        ]
    }
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_clusters = AsyncMock(return_value=mock_resp)
        result = await filter_clusters_by_tag("env", "production")
        parsed = json.loads(result)
        assert parsed["matched"] == 1
        assert parsed["clusters"][0]["id"] == "o-1"


@pytest.mark.asyncio
async def test_filter_clusters_by_tag_key_only():
    """filter_clusters_by_tag with no value matches any value for that key."""
    mock_resp = {
        "items": [
            {"id": "o-1", "tags": [{"tagKey": "team", "tagValue": "infra"}]},
            {"id": "o-2", "tags": [{"tagKey": "team", "tagValue": "ml"}]},
            {"id": "o-3", "tags": [{"tagKey": "other", "tagValue": "x"}]},
        ]
    }
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_clusters = AsyncMock(return_value=mock_resp)
        result = await filter_clusters_by_tag("team")
        parsed = json.loads(result)
        assert parsed["matched"] == 2


@pytest.mark.asyncio
async def test_filter_vngs_by_tag_matches():
    """filter_vngs_by_tag should match VNGs with matching tags."""
    mock_resp = {
        "items": [
            {"id": "ols-1", "tags": [{"tagKey": "workload", "tagValue": "gpu"}]},
            {"id": "ols-2", "tags": [{"tagKey": "workload", "tagValue": "cpu"}]},
        ]
    }
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_vngs = AsyncMock(return_value=mock_resp)
        result = await filter_vngs_by_tag("workload", "gpu")
        parsed = json.loads(result)
        assert parsed["matched"] == 1
        assert parsed["vngs"][0]["id"] == "ols-1"


@pytest.mark.asyncio
async def test_export_cluster_yaml_format():
    """export_cluster_yaml should return valid YAML."""
    import yaml
    mock_resp = {"items": [{"id": "o-abc", "name": "test", "region": "us-west-2", "autoScaler": {"isEnabled": True}}]}
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.get_cluster = AsyncMock(return_value=mock_resp)
        result = await export_cluster_yaml("o-abc")
        parsed = yaml.safe_load(result)
        assert parsed["id"] == "o-abc"
        assert parsed["autoScaler"]["isEnabled"] is True


@pytest.mark.asyncio
async def test_right_sizing_azure_uses_post():
    """get_right_sizing with cloud=azure should call the Azure POST endpoint."""
    mock_resp = {"items": [{"deploymentName": "nginx", "suggestedCPU": 100}]}
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.get_right_sizing_azure = AsyncMock(return_value=mock_resp)
        result = await get_right_sizing("o-abc", cloud="azure")
        parsed = json.loads(result)
        assert parsed["items"][0]["deploymentName"] == "nginx"
        mock_client.return_value.get_right_sizing_azure.assert_called_once()


@pytest.mark.asyncio
async def test_list_stateful_nodes_azure():
    """list_stateful_nodes_azure should return Azure stateful nodes."""
    mock_resp = {"items": [{"id": "ssn-abc", "name": "test-vm"}], "count": 1}
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_stateful_nodes_azure = AsyncMock(return_value=mock_resp)
        result = await list_stateful_nodes_azure()
        parsed = json.loads(result)
        assert parsed["items"][0]["id"] == "ssn-abc"


@pytest.mark.asyncio
async def test_get_cluster_scheduling_extracts_fields():
    """get_cluster_scheduling should return only scheduling and autoScaler."""
    mock_resp = {
        "items": [{
            "id": "o-abc",
            "name": "test",
            "region": "us-west-2",
            "scheduling": {"shutdownHours": {"isEnabled": True, "timeWindows": ["Sat:00:00-Sun:23:59"]}},
            "autoScaler": {"isEnabled": True, "cooldown": 300},
            "compute": {"launchSpecification": {}},
        }]
    }
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.get_cluster_scheduling = AsyncMock(return_value=mock_resp)
        result = await get_cluster_scheduling("o-abc")
        parsed = json.loads(result)
        assert "scheduling" in parsed
        assert "autoScaler" in parsed
        assert "compute" not in parsed
        assert parsed["scheduling"]["shutdownHours"]["isEnabled"] is True
