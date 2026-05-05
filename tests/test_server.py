"""Tests for the MCP server tool registration and safety guards."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_server_spotinst.server import (
    _diff_submitted_vs_readback,
    _extract_launchspec,
    _looks_like_base64,
    _truncate_items,
    create_vng,
    delete_vng,
    export_cluster_yaml,
    filter_clusters_by_tag,
    filter_vngs_by_tag,
    get_cluster_scheduling,
    get_right_sizing,
    list_all_clusters,
    list_clusters,
    list_stateful_nodes_azure,
    list_vngs,
    mcp,
    remove_instances,
    update_vng,
)


def test_looks_like_base64():
    """_looks_like_base64 should distinguish base64 from raw text."""
    import base64
    assert _looks_like_base64(base64.b64encode(b"hello").decode())
    assert _looks_like_base64(base64.b64encode(b"#!/bin/bash\nset -e\n").decode())
    # Raw shell script should NOT be mistaken for base64
    assert not _looks_like_base64("#!/bin/bash\nset -e\necho hi")
    assert not _looks_like_base64("just plain text here with spaces")
    # Empty string is "already encoded" (no-op)
    assert _looks_like_base64("")


@pytest.mark.asyncio
async def test_update_vng_auto_encodes_userdata():
    """update_vng should auto base64-encode plaintext userData."""
    import base64
    captured = {}

    async def fake_update(vng_id, updates, account_id, auto_apply_tags=None):
        captured["updates"] = updates
        return {"items": [{"id": vng_id}]}

    async def fake_get_vng(vng_id, account_id):
        return {"items": [{"id": vng_id}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.update_vng = AsyncMock(side_effect=fake_update)
        mock_client.return_value.get_vng = AsyncMock(side_effect=fake_get_vng)
        plaintext = "#!/bin/bash\nset -e\necho hello"
        await update_vng(
            "ols-abc",
            json.dumps({"userData": plaintext}),
            confirm=True,
        )
    sent = captured["updates"]["userData"]
    assert sent != plaintext, "userData should have been base64-encoded"
    assert base64.b64decode(sent).decode() == plaintext


@pytest.mark.asyncio
async def test_update_vng_skips_encode_when_already_base64():
    """update_vng should NOT double-encode already-base64 userData."""
    import base64
    captured = {}

    async def fake_update(vng_id, updates, account_id, auto_apply_tags=None):
        captured["updates"] = updates
        return {"items": [{"id": vng_id}]}

    async def fake_get_vng(vng_id, account_id):
        return {"items": [{"id": vng_id}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.update_vng = AsyncMock(side_effect=fake_update)
        mock_client.return_value.get_vng = AsyncMock(side_effect=fake_get_vng)
        already = base64.b64encode(b"#!/bin/bash\nset -e\n").decode()
        await update_vng(
            "ols-abc",
            json.dumps({"userData": already}),
            confirm=True,
        )
    assert captured["updates"]["userData"] == already


@pytest.mark.asyncio
async def test_update_vng_opt_out_encoding():
    """encode_user_data=False should pass userData through unchanged."""
    captured = {}

    async def fake_update(vng_id, updates, account_id, auto_apply_tags=None):
        captured["updates"] = updates
        return {"items": [{"id": vng_id}]}

    async def fake_get_vng(vng_id, account_id):
        return {"items": [{"id": vng_id}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.update_vng = AsyncMock(side_effect=fake_update)
        mock_client.return_value.get_vng = AsyncMock(side_effect=fake_get_vng)
        raw = "raw-thing-not-base64"
        await update_vng(
            "ols-abc",
            json.dumps({"userData": raw}),
            confirm=True,
            encode_user_data=False,
        )
    assert captured["updates"]["userData"] == raw


@pytest.mark.asyncio
async def test_update_vng_returns_readback():
    """Response should include both put_result and readback so callers verify the change landed."""
    async def fake_update(vng_id, updates, account_id, auto_apply_tags=None):
        return {"items": [{"id": vng_id, "updateReceived": True}]}

    async def fake_get_vng(vng_id, account_id):
        return {"items": [{"id": vng_id, "resourceLimits": {"maxInstanceCount": 20}}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.update_vng = AsyncMock(side_effect=fake_update)
        mock_client.return_value.get_vng = AsyncMock(side_effect=fake_get_vng)
        result = await update_vng(
            "ols-abc",
            json.dumps({"resourceLimits": {"maxInstanceCount": 20}}),
            confirm=True,
        )
    parsed = json.loads(result)
    assert "put_result" in parsed
    assert "readback" in parsed
    assert parsed["readback"]["items"][0]["resourceLimits"]["maxInstanceCount"] == 20


@pytest.mark.asyncio
async def test_update_vng_readback_error_captured():
    """If readback fails, response should surface the error instead of re-raising."""
    async def fake_update(vng_id, updates, account_id, auto_apply_tags=None):
        return {"items": [{"id": vng_id}]}

    async def fake_get_vng(vng_id, account_id):
        raise RuntimeError("readback failed")

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.update_vng = AsyncMock(side_effect=fake_update)
        mock_client.return_value.get_vng = AsyncMock(side_effect=fake_get_vng)
        result = await update_vng(
            "ols-abc",
            json.dumps({"tags": []}),
            confirm=True,
        )
    parsed = json.loads(result)
    assert "_readback_error" in parsed["readback"]
    assert "readback failed" in parsed["readback"]["_readback_error"]


def test_extract_launchspec_direct_items():
    assert _extract_launchspec({"items": [{"id": "ols-1"}]}) == {"id": "ols-1"}


def test_extract_launchspec_nested_response():
    payload = {"response": {"items": [{"id": "ols-2"}]}}
    assert _extract_launchspec(payload) == {"id": "ols-2"}


def test_extract_launchspec_none_on_unknown_shape():
    assert _extract_launchspec({}) is None
    assert _extract_launchspec({"items": []}) is None
    assert _extract_launchspec(None) is None


def test_diff_submitted_vs_readback_empty_when_fields_match():
    submitted = {"resourceLimits": {"maxInstanceCount": 20}}
    readback = {"items": [{"resourceLimits": {"maxInstanceCount": 20}}]}
    assert _diff_submitted_vs_readback(submitted, readback) == {}


def test_diff_submitted_vs_readback_flags_missing_field():
    submitted = {"resourceLimits": {"maxInstanceCount": 20}}
    readback = {"items": [{"id": "ols-1"}]}
    diff = _diff_submitted_vs_readback(submitted, readback)
    assert "resourceLimits" in diff
    assert diff["resourceLimits"]["observed"] is None


def test_diff_submitted_vs_readback_flags_value_drift():
    submitted = {"resourceLimits": {"maxInstanceCount": 20}}
    readback = {"items": [{"resourceLimits": {"maxInstanceCount": 10}}]}
    diff = _diff_submitted_vs_readback(submitted, readback)
    assert diff["resourceLimits"]["sent"] == {"maxInstanceCount": 20}
    assert diff["resourceLimits"]["observed"] == {"maxInstanceCount": 10}


def test_diff_submitted_vs_readback_userdata_roundtrip_match():
    import base64
    payload = "#!/bin/bash\necho hi\n"
    encoded = base64.b64encode(payload.encode()).decode()
    submitted = {"userData": encoded}
    readback = {"items": [{"userData": encoded}]}
    assert _diff_submitted_vs_readback(submitted, readback) == {}


def test_diff_submitted_vs_readback_userdata_silent_non_persist():
    """Regression: mirrors the 2026-05-05 incident where Spot bumped
    updatedAt but silently kept the old userData body."""
    import base64
    sent_body = b"#!/bin/bash\nset -uo pipefail\nwait_for_apt\n"
    old_body = b"#!/bin/bash\nset -ex\napt-get update\n"
    submitted = {"userData": base64.b64encode(sent_body).decode()}
    readback = {"items": [{"userData": base64.b64encode(old_body).decode()}]}
    diff = _diff_submitted_vs_readback(submitted, readback)
    assert "userData" in diff
    assert diff["userData"]["sent_bytes"] == len(sent_body)
    assert diff["userData"]["observed_bytes"] == len(old_body)


@pytest.mark.asyncio
async def test_update_vng_flags_readback_mismatch():
    """When userData silently doesn't persist, response must include _readback_mismatch."""
    import base64
    sent_body = b"#!/bin/bash\nset -uo pipefail\n"
    old_body = b"#!/bin/bash\nset -ex\n"

    async def fake_update(vng_id, updates, account_id, auto_apply_tags=None):
        return {"items": [{"id": vng_id, "updatedAt": "2026-05-05T13:10:59Z"}]}

    async def fake_get_vng(vng_id, account_id):
        return {"items": [{"id": vng_id, "userData": base64.b64encode(old_body).decode()}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.update_vng = AsyncMock(side_effect=fake_update)
        mock_client.return_value.get_vng = AsyncMock(side_effect=fake_get_vng)
        result = await update_vng(
            "ols-abc",
            json.dumps({"userData": base64.b64encode(sent_body).decode()}),
            confirm=True,
            encode_user_data=False,
        )
    parsed = json.loads(result)
    assert "_readback_mismatch" in parsed
    assert "userData" in parsed["_readback_mismatch"]
    assert parsed["_readback_mismatch"]["userData"]["sent_bytes"] == len(sent_body)


@pytest.mark.asyncio
async def test_update_vng_no_mismatch_when_userdata_persists():
    """Happy path: readback matches submitted userData, no _readback_mismatch emitted."""
    import base64
    body = b"#!/bin/bash\nset -uo pipefail\n"
    encoded = base64.b64encode(body).decode()

    async def fake_update(vng_id, updates, account_id, auto_apply_tags=None):
        return {"items": [{"id": vng_id}]}

    async def fake_get_vng(vng_id, account_id):
        return {"items": [{"id": vng_id, "userData": encoded}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.update_vng = AsyncMock(side_effect=fake_update)
        mock_client.return_value.get_vng = AsyncMock(side_effect=fake_get_vng)
        result = await update_vng(
            "ols-abc",
            json.dumps({"userData": encoded}),
            confirm=True,
            encode_user_data=False,
        )
    parsed = json.loads(result)
    assert "_readback_mismatch" not in parsed


def test_all_tools_registered():
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    assert len(tools) == 39  # 32 read + 7 write
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


def test_truncate_items_truncates_and_adds_metadata():
    """_truncate_items should truncate and add metadata."""
    data = {"items": [{"id": i} for i in range(100)]}
    result = _truncate_items(data, 10)
    assert len(result["items"]) == 10
    assert result["_truncated"] is True
    assert result["_total_count"] == 100
    assert result["_showing"] == 10


def test_truncate_items_no_truncation_when_under_limit():
    """_truncate_items should not truncate when items <= limit."""
    data = {"items": [{"id": 1}, {"id": 2}]}
    result = _truncate_items(data, 10)
    assert "_truncated" not in result
    assert len(result["items"]) == 2


def test_truncate_items_limit_zero_returns_all():
    """_truncate_items with limit=0 should return all items."""
    data = {"items": [{"id": i} for i in range(100)]}
    result = _truncate_items(data, 0)
    assert "_truncated" not in result
    assert len(result["items"]) == 100


def test_truncate_items_with_sort_key():
    """_truncate_items should sort by sort_key before truncating."""
    data = {"items": [{"id": i, "val": i} for i in range(10)]}
    result = _truncate_items(data, 3, sort_key=lambda x: x["val"])
    assert [item["val"] for item in result["items"]] == [9, 8, 7]


@pytest.mark.asyncio
async def test_get_right_sizing_truncation():
    """get_right_sizing should truncate and sort by CPU delta."""
    items = [
        {"id": f"w-{i}", "requestedCPU": i * 100, "suggestedCPU": 50}
        for i in range(10)
    ]
    mock_resp = {"items": items}
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.get_right_sizing = AsyncMock(return_value=mock_resp)
        result = await get_right_sizing("o-abc", limit=3)
        parsed = json.loads(result)
        assert parsed["_truncated"] is True
        assert parsed["_total_count"] == 10
        assert parsed["_showing"] == 3
        # Should be sorted by biggest CPU delta first (highest requestedCPU)
        assert parsed["items"][0]["requestedCPU"] == 900


@pytest.mark.asyncio
async def test_get_right_sizing_limit_zero():
    """get_right_sizing with limit=0 should return all items."""
    items = [{"id": f"w-{i}", "requestedCPU": i * 100, "suggestedCPU": 50} for i in range(10)]
    mock_resp = {"items": items}
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.get_right_sizing = AsyncMock(return_value=mock_resp)
        result = await get_right_sizing("o-abc", limit=0)
        parsed = json.loads(result)
        assert "_truncated" not in parsed
        assert len(parsed["items"]) == 10


@pytest.mark.asyncio
async def test_list_all_clusters_compact_by_default():
    """list_all_clusters should return compact summaries by default."""
    mock_clusters = [
        {
            "id": "o-abc123",
            "name": "prod-cluster",
            "controllerClusterId": "prod-k8s",
            "region": "us-east-1",
            "capacity": {"minimum": 1, "maximum": 10, "target": 3},
            "_accountId": "act-111",
            "_accountName": "Prod Account",
            "_cloudProvider": "AWS",
            "autoScaler": {"isEnabled": True, "cooldown": 300},
            "compute": {"subnetIds": ["subnet-aaa"], "instanceTypes": {"whitelist": ["m5.xlarge"]}},
            "strategy": {"spotPercentage": 80},
        },
        {
            "id": "o-def456",
            "name": "dev-azure",
            "aks": {"name": "dev-aks", "resourceGroupName": "rg-dev"},
            "capacity": {"minimum": 1, "maximum": 5, "target": 2},
            "_accountId": "act-222",
            "_accountName": "Dev Azure",
            "_cloudProvider": "AZURE",
            "autoScaler": {"isEnabled": False},
            "virtualNodeGroupTemplate": {"big": "nested object"},
        },
    ]
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_all_clusters = AsyncMock(return_value=mock_clusters)
        result = await list_all_clusters()
        parsed = json.loads(result)
        assert parsed["_summary"] is True
        assert "verbose=true" in parsed["_hint"]
        assert "_verbose_when" in parsed
        assert len(parsed["items"]) == 2
        # AWS cluster: core fields kept, bloat stripped
        aws = parsed["items"][0]
        assert aws["id"] == "o-abc123"
        assert aws["_accountId"] == "act-111"
        assert aws["region"] == "us-east-1"
        assert aws["capacity"]["target"] == 3
        assert "autoScaler" not in aws
        assert "compute" not in aws
        assert "strategy" not in aws
        # Azure cluster: AKS fields extracted
        azure = parsed["items"][1]
        assert azure["id"] == "o-def456"
        assert azure["_accountId"] == "act-222"
        assert azure["resourceGroupName"] == "rg-dev"
        assert "virtualNodeGroupTemplate" not in azure


@pytest.mark.asyncio
async def test_list_all_clusters_verbose_returns_full():
    """list_all_clusters with verbose=True should return full configs."""
    mock_clusters = [
        {
            "id": "o-abc123",
            "name": "prod",
            "_accountId": "act-111",
            "_accountName": "Prod",
            "_cloudProvider": "AWS",
            "autoScaler": {"isEnabled": True},
            "compute": {"subnetIds": ["subnet-aaa"]},
        },
    ]
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_all_clusters = AsyncMock(return_value=mock_clusters)
        result = await list_all_clusters(verbose=True)
        parsed = json.loads(result)
        # Should be a flat list, no _summary metadata
        assert isinstance(parsed, list)
        assert "autoScaler" in parsed[0]
        assert "compute" in parsed[0]


@pytest.mark.asyncio
async def test_list_clusters_compact():
    """list_clusters should return compact summaries by default."""
    mock_resp = {
        "items": [
            {
                "id": "o-abc",
                "name": "prod",
                "region": "us-west-2",
                "capacity": {"minimum": 1, "maximum": 10, "target": 3},
                "autoScaler": {"isEnabled": True},
                "compute": {"subnetIds": ["subnet-x"]},
            },
        ]
    }
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_clusters = AsyncMock(return_value=mock_resp)
        result = await list_clusters()
        parsed = json.loads(result)
        assert parsed["_summary"] is True
        cluster = parsed["items"][0]
        assert cluster["id"] == "o-abc"
        assert cluster["region"] == "us-west-2"
        assert "autoScaler" not in cluster
        assert "compute" not in cluster


@pytest.mark.asyncio
async def test_list_vngs_compact():
    """list_vngs should return compact summaries with oceanId."""
    mock_resp = {
        "items": [
            {
                "id": "ols-abc",
                "name": "gpu-vng",
                "oceanId": "o-123",
                "imageId": "ami-xxx",
                "resourceLimits": {"maxInstanceCount": 100},
            },
        ]
    }
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_vngs = AsyncMock(return_value=mock_resp)
        result = await list_vngs()
        parsed = json.loads(result)
        assert parsed["_summary"] is True
        vng = parsed["items"][0]
        assert vng["id"] == "ols-abc"
        assert vng["oceanId"] == "o-123"
        assert "imageId" not in vng
        assert "resourceLimits" not in vng


@pytest.mark.asyncio
async def test_filter_clusters_by_tag_compact():
    """filter_clusters_by_tag should return compact summaries by default."""
    mock_resp = {
        "items": [
            {
                "id": "o-1",
                "name": "prod",
                "region": "us-west-2",
                "tags": [{"tagKey": "env", "tagValue": "production"}],
                "autoScaler": {"isEnabled": True},
                "compute": {"big": "data"},
            },
        ]
    }
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.list_clusters = AsyncMock(return_value=mock_resp)
        result = await filter_clusters_by_tag("env", "production")
        parsed = json.loads(result)
        assert parsed["matched"] == 1
        cluster = parsed["clusters"][0]
        assert cluster["id"] == "o-1"
        assert "autoScaler" not in cluster
        assert "compute" not in cluster


# --- create_vng / delete_vng tools ---


@pytest.mark.asyncio
async def test_create_vng_safety_guard():
    """Without confirm=true, create_vng should return a SAFETY preview and not call the API."""
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.create_vng = AsyncMock()
        result = await create_vng("o-parent", json.dumps({"name": "test"}))
        assert "SAFETY" in result
        mock_client.return_value.create_vng.assert_not_called()


@pytest.mark.asyncio
async def test_create_vng_rejects_ocean_id_in_spec():
    """oceanId in spec_json is ambiguous — should be rejected."""
    result = await create_vng(
        "o-parent",
        json.dumps({"oceanId": "o-other", "name": "test"}),
        confirm=True,
    )
    assert "ERROR" in result
    assert "oceanId" in result


@pytest.mark.asyncio
async def test_create_vng_invalid_json():
    result = await create_vng("o-parent", "not-json{", confirm=True)
    assert "ERROR" in result


@pytest.mark.asyncio
async def test_create_vng_auto_encodes_userdata():
    """create_vng should base64-encode plaintext userData like update_vng does."""
    import base64
    captured = {}

    async def fake_create(ocean_id, spec, account_id="", initial_nodes=None):
        captured["spec"] = spec
        return {"items": [{"id": "ols-new"}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.create_vng = AsyncMock(side_effect=fake_create)
        plaintext = "#!/bin/bash\nset -e\necho new-vng"
        await create_vng(
            "o-parent",
            json.dumps({"name": "test", "userData": plaintext}),
            confirm=True,
        )
    sent = captured["spec"]["userData"]
    assert sent != plaintext
    assert base64.b64decode(sent).decode() == plaintext


@pytest.mark.asyncio
async def test_create_vng_executes_on_confirm():
    """confirm=true should actually call create_vng on the client."""
    async def fake_create(ocean_id, spec, account_id="", initial_nodes=None):
        return {"items": [{"id": "ols-new", "oceanId": ocean_id, "name": spec["name"]}]}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.create_vng = AsyncMock(side_effect=fake_create)
        result = await create_vng(
            "o-parent",
            json.dumps({"name": "my-vng", "instanceTypes": ["m5.large"]}),
            confirm=True,
            initial_nodes=0,
        )
    parsed = json.loads(result)
    assert parsed["items"][0]["id"] == "ols-new"
    assert parsed["items"][0]["oceanId"] == "o-parent"


@pytest.mark.asyncio
async def test_delete_vng_safety_guard():
    """Without confirm=true, delete_vng should return a SAFETY preview and not call the API."""
    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.delete_vng = AsyncMock()
        result = await delete_vng("ols-del")
        assert "SAFETY" in result
        mock_client.return_value.delete_vng.assert_not_called()


@pytest.mark.asyncio
async def test_delete_vng_preview_mentions_delete_nodes():
    """When delete_nodes=true, the safety preview should flag node termination."""
    result = await delete_vng("ols-del", delete_nodes=True)
    assert "SAFETY" in result
    assert "drain" in result.lower() or "terminate" in result.lower()


@pytest.mark.asyncio
async def test_delete_vng_executes_on_confirm():
    """confirm=true should call delete_vng with all flags forwarded."""
    captured = {}

    async def fake_delete(vng_id, account_id="", delete_nodes=False, force_delete=False):
        captured.update(
            vng_id=vng_id,
            delete_nodes=delete_nodes,
            force_delete=force_delete,
        )
        return {"deleted": True, "id": vng_id}

    with patch("mcp_server_spotinst.server._get_client") as mock_client:
        mock_client.return_value.delete_vng = AsyncMock(side_effect=fake_delete)
        await delete_vng(
            "ols-del",
            confirm=True,
            delete_nodes=True,
            force_delete=True,
        )
    assert captured == {"vng_id": "ols-del", "delete_nodes": True, "force_delete": True}
