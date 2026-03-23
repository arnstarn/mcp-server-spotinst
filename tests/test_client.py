"""Tests for the Spotinst API client using mocked HTTP responses."""

import httpx
import pytest
import respx

from mcp_server_spotinst.spotinst_client import SpotinstClient


def _api_response(items: list, kind: str = "spotinst:test") -> dict:
    return {
        "request": {"id": "test", "url": "/test", "method": "GET"},
        "response": {
            "status": {"code": 200, "message": "OK"},
            "kind": kind,
            "items": items,
            "count": len(items),
        },
    }


@pytest.fixture
def client():
    return SpotinstClient(token="test-token", account_id="act-test123")


@respx.mock
@pytest.mark.asyncio
async def test_list_clusters(client: SpotinstClient):
    clusters = [{"id": "o-abc123", "name": "test-cluster"}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster").mock(
        return_value=httpx.Response(200, json=_api_response(clusters))
    )
    result = await client.list_clusters()
    assert result["items"][0]["id"] == "o-abc123"


@respx.mock
@pytest.mark.asyncio
async def test_list_clusters_azure(client: SpotinstClient):
    clusters = [{"id": "o-azure1", "name": "azure-cluster"}]
    respx.get("https://api.spotinst.io/ocean/azure/np/cluster").mock(
        return_value=httpx.Response(200, json=_api_response(clusters))
    )
    result = await client.list_clusters_azure()
    assert result["items"][0]["id"] == "o-azure1"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster(client: SpotinstClient):
    cluster = [{"id": "o-abc123", "name": "test-cluster", "region": "us-west-2"}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123").mock(
        return_value=httpx.Response(200, json=_api_response(cluster))
    )
    result = await client.get_cluster("o-abc123")
    assert result["items"][0]["region"] == "us-west-2"


@respx.mock
@pytest.mark.asyncio
async def test_list_vngs(client: SpotinstClient):
    vngs = [{"id": "ols-abc", "name": "gpu"}, {"id": "ols-def", "name": "cpu"}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/launchSpec").mock(
        return_value=httpx.Response(200, json=_api_response(vngs))
    )
    result = await client.list_vngs("o-abc123")
    assert len(result["items"]) == 2


@respx.mock
@pytest.mark.asyncio
async def test_list_vngs_azure(client: SpotinstClient):
    vngs = [{"id": "vng-abc", "name": "pool1"}]
    respx.get("https://api.spotinst.io/ocean/azure/np/virtualNodeGroup").mock(
        return_value=httpx.Response(200, json=_api_response(vngs))
    )
    result = await client.list_vngs_azure()
    assert result["items"][0]["id"] == "vng-abc"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_nodes(client: SpotinstClient):
    nodes = [{"instanceId": "i-abc", "lifeCycle": "Spot", "instanceType": "c5.xlarge"}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/nodes").mock(
        return_value=httpx.Response(200, json=_api_response(nodes))
    )
    result = await client.get_cluster_nodes("o-abc123")
    assert result["items"][0]["lifeCycle"] == "Spot"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_nodes_azure(client: SpotinstClient):
    nodes = [{"vmName": "vm-abc"}]
    respx.get("https://api.spotinst.io/ocean/azure/np/cluster/o-az1/nodes").mock(
        return_value=httpx.Response(200, json=_api_response(nodes))
    )
    result = await client.get_cluster_nodes("o-az1", cloud="azure")
    assert result["items"][0]["vmName"] == "vm-abc"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_costs(client: SpotinstClient):
    costs = [{"result": {"totalForDuration": {"summary": {"total": 1234.56}}}}]
    respx.post(
        "https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/aggregatedCosts"
    ).mock(return_value=httpx.Response(200, json=_api_response(costs)))
    result = await client.get_cluster_costs(
        "o-abc123", "2026-03-01T00:00:00Z", "2026-03-20T00:00:00Z"
    )
    assert result["items"][0]["result"]["totalForDuration"]["summary"]["total"] == 1234.56


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_costs_azure(client: SpotinstClient):
    costs = [{"result": {}}]
    respx.post(
        "https://api.spotinst.io/ocean/azure/k8s/cluster/o-az1/aggregatedCosts"
    ).mock(return_value=httpx.Response(200, json=_api_response(costs)))
    result = await client.get_cluster_costs(
        "o-az1", "2026-03-01T00:00:00Z", "2026-03-20T00:00:00Z", cloud="azure"
    )
    assert "items" in result


@respx.mock
@pytest.mark.asyncio
async def test_list_rolls(client: SpotinstClient):
    rolls = [{"id": "scr-abc", "status": "COMPLETED"}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/roll").mock(
        return_value=httpx.Response(200, json=_api_response(rolls))
    )
    result = await client.list_rolls("o-abc123")
    assert result["items"][0]["status"] == "COMPLETED"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_log(client: SpotinstClient):
    logs = [{"message": "Scale up", "severity": "INFO"}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/log").mock(
        return_value=httpx.Response(200, json=_api_response(logs))
    )
    result = await client.get_cluster_log("o-abc123", "2026-03-20", "2026-03-20")
    assert result["items"][0]["severity"] == "INFO"


@respx.mock
@pytest.mark.asyncio
async def test_list_accounts(client: SpotinstClient):
    accounts = [
        {"accountId": "act-abc", "name": "Dev", "cloudProvider": "AWS"},
        {"accountId": "act-def", "name": "Prod", "cloudProvider": "AZURE"},
    ]
    respx.get("https://api.spotinst.io/setup/account").mock(
        return_value=httpx.Response(200, json=_api_response(accounts))
    )
    result = await client.list_accounts()
    assert len(result["items"]) == 2


@respx.mock
@pytest.mark.asyncio
async def test_list_all_clusters(client: SpotinstClient):
    accounts = [
        {"accountId": "act-aws1", "name": "AWS Account", "cloudProvider": "AWS"},
        {"accountId": "act-az1", "name": "Azure Account", "cloudProvider": "AZURE"},
    ]
    aws_clusters = [{"id": "o-aws1", "name": "aws-cluster"}]
    azure_clusters = [{"id": "o-az1", "name": "azure-cluster"}]

    respx.get("https://api.spotinst.io/setup/account").mock(
        return_value=httpx.Response(200, json=_api_response(accounts))
    )
    respx.get(
        "https://api.spotinst.io/ocean/aws/k8s/cluster",
        params__contains={"accountId": "act-aws1"},
    ).mock(return_value=httpx.Response(200, json=_api_response(aws_clusters)))
    respx.get(
        "https://api.spotinst.io/ocean/azure/np/cluster",
        params__contains={"accountId": "act-az1"},
    ).mock(return_value=httpx.Response(200, json=_api_response(azure_clusters)))

    clusters = await client.list_all_clusters()
    assert len(clusters) == 2
    providers = {c["_cloudProvider"] for c in clusters}
    assert providers == {"AWS", "AZURE"}


@respx.mock
@pytest.mark.asyncio
async def test_account_id_override(client: SpotinstClient):
    """Verify account_id parameter overrides the default."""
    clusters = [{"id": "o-prod1", "name": "prod-cluster"}]
    route = respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster").mock(
        return_value=httpx.Response(200, json=_api_response(clusters))
    )
    await client.list_clusters("act-override")
    assert route.calls[0].request.url.params["accountId"] == "act-override"


@respx.mock
@pytest.mark.asyncio
async def test_initiate_roll(client: SpotinstClient):
    """Verify initiate_roll calls the correct endpoint."""
    respx.post("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/roll").mock(
        return_value=httpx.Response(
            200, json=_api_response([{"id": "scr-new", "status": "IN_PROGRESS"}])
        )
    )
    result = await client.initiate_roll("o-abc123")
    assert result["items"][0]["status"] == "IN_PROGRESS"


@respx.mock
@pytest.mark.asyncio
async def test_list_stateful_nodes(client: SpotinstClient):
    nodes = [{"id": "smi-abc", "name": "my-stateful", "state": "ACTIVE"}]
    respx.get("https://api.spotinst.io/aws/ec2/managedInstance").mock(
        return_value=httpx.Response(200, json=_api_response(nodes))
    )
    result = await client.list_stateful_nodes()
    assert result["items"][0]["id"] == "smi-abc"


@respx.mock
@pytest.mark.asyncio
async def test_get_stateful_node(client: SpotinstClient):
    node = [{"id": "smi-abc", "name": "my-stateful", "state": "ACTIVE", "region": "us-east-1"}]
    respx.get("https://api.spotinst.io/aws/ec2/managedInstance/smi-abc").mock(
        return_value=httpx.Response(200, json=_api_response(node))
    )
    result = await client.get_stateful_node("smi-abc")
    assert result["items"][0]["region"] == "us-east-1"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_health(client: SpotinstClient):
    """Verify composite health check gathers nodes, logs, and rolls."""
    nodes = [
        {"instanceId": "i-1", "lifeCycle": "Spot"},
        {"instanceId": "i-2", "lifeCycle": "Spot"},
        {"instanceId": "i-3", "lifeCycle": "OD"},
    ]
    logs = [
        {"message": "Scale up", "severity": "INFO"},
        {"message": "Failed", "severity": "ERROR"},
    ]
    rolls = [{"id": "scr-1", "status": "COMPLETED"}]

    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/nodes").mock(
        return_value=httpx.Response(200, json=_api_response(nodes))
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/log").mock(
        return_value=httpx.Response(200, json=_api_response(logs))
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/roll").mock(
        return_value=httpx.Response(200, json=_api_response(rolls))
    )

    result = await client.get_cluster_health("o-abc123")
    assert result["nodes"]["total"] == 3
    assert result["nodes"]["by_lifecycle"]["Spot"] == 2
    assert result["nodes"]["by_lifecycle"]["OD"] == 1
    assert result["logs_24h"]["errors"] == 1
    assert result["rolls"]["total"] == 1
    assert result["rolls"]["active"] == 0
    assert result["health"] == "OK"


@respx.mock
@pytest.mark.asyncio
async def test_get_cost_trending(client: SpotinstClient):
    """Verify cost trending fetches multiple periods."""
    costs = [{"result": {"totalForDuration": {"summary": {"total": 100.0}}}}]
    respx.post(url__regex=r".*/aggregatedCosts").mock(
        return_value=httpx.Response(200, json=_api_response(costs))
    )
    result = await client.get_cost_trending("o-abc123", periods=2, period_days=7)
    assert len(result) == 2
    assert "period" in result[0]


# --- Additional coverage ---


@respx.mock
@pytest.mark.asyncio
async def test_get_safe_returns_none_on_400(client: SpotinstClient):
    """_get_safe should return None on 400 instead of raising."""
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster").mock(
        return_value=httpx.Response(400, json={"error": "bad request"})
    )
    result = await client._get_safe("/ocean/aws/k8s/cluster")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_get_safe_returns_none_on_404(client: SpotinstClient):
    """_get_safe should return None on 404."""
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-missing").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    result = await client._get_safe("/ocean/aws/k8s/cluster/o-missing")
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_post_safe_returns_none_on_400(client: SpotinstClient):
    """_post_safe should return None on 400."""
    respx.post("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc/aggregatedCosts").mock(
        return_value=httpx.Response(400, json={"error": "bad request"})
    )
    result = await client._post_safe("/ocean/aws/k8s/cluster/o-abc/aggregatedCosts", {"startTime": "x", "endTime": "y"})
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_get_vng(client: SpotinstClient):
    vng = [{"id": "ols-abc", "name": "gpu", "oceanId": "o-abc123", "instanceTypes": ["g4dn.xlarge"]}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/launchSpec/ols-abc").mock(
        return_value=httpx.Response(200, json=_api_response(vng))
    )
    result = await client.get_vng("ols-abc")
    assert result["items"][0]["name"] == "gpu"


@respx.mock
@pytest.mark.asyncio
async def test_get_vng_azure(client: SpotinstClient):
    vng = [{"id": "vng-abc", "name": "pool1"}]
    respx.get("https://api.spotinst.io/ocean/azure/np/virtualNodeGroup/vng-abc").mock(
        return_value=httpx.Response(200, json=_api_response(vng))
    )
    result = await client.get_vng_azure("vng-abc")
    assert result["items"][0]["id"] == "vng-abc"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_azure(client: SpotinstClient):
    cluster = [{"id": "o-az1", "name": "azure-prod", "aks": {"clusterName": "prod"}}]
    respx.get("https://api.spotinst.io/ocean/azure/np/cluster/o-az1").mock(
        return_value=httpx.Response(200, json=_api_response(cluster))
    )
    result = await client.get_cluster_azure("o-az1")
    assert result["items"][0]["aks"]["clusterName"] == "prod"


@respx.mock
@pytest.mark.asyncio
async def test_list_elastigroups(client: SpotinstClient):
    groups = [{"id": "sig-abc", "name": "web-servers", "capacity": {"minimum": 1, "maximum": 10}}]
    respx.get("https://api.spotinst.io/aws/ec2/group").mock(
        return_value=httpx.Response(200, json=_api_response(groups))
    )
    result = await client.list_elastigroups()
    assert result["items"][0]["id"] == "sig-abc"


@respx.mock
@pytest.mark.asyncio
async def test_get_elastigroup(client: SpotinstClient):
    group = [{"id": "sig-abc", "name": "web-servers", "region": "us-east-1"}]
    respx.get("https://api.spotinst.io/aws/ec2/group/sig-abc").mock(
        return_value=httpx.Response(200, json=_api_response(group))
    )
    result = await client.get_elastigroup("sig-abc")
    assert result["items"][0]["region"] == "us-east-1"


@respx.mock
@pytest.mark.asyncio
async def test_get_right_sizing(client: SpotinstClient):
    suggestions = [{"namespace": "default", "containers": [{"name": "app", "suggestedCpu": 0.5}]}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/rightSizing/resourceSuggestion").mock(
        return_value=httpx.Response(200, json=_api_response(suggestions))
    )
    result = await client.get_right_sizing("o-abc123")
    assert result["items"][0]["namespace"] == "default"


@respx.mock
@pytest.mark.asyncio
async def test_get_right_sizing_with_namespace(client: SpotinstClient):
    suggestions = [{"namespace": "kube-system", "containers": []}]
    route = respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/rightSizing/resourceSuggestion").mock(
        return_value=httpx.Response(200, json=_api_response(suggestions))
    )
    await client.get_right_sizing("o-abc123", namespace="kube-system")
    assert route.calls[0].request.url.params["namespace"] == "kube-system"


@respx.mock
@pytest.mark.asyncio
async def test_get_roll(client: SpotinstClient):
    roll = [{"id": "scr-abc", "status": "COMPLETED", "progress": {"value": 100}}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/roll/scr-abc").mock(
        return_value=httpx.Response(200, json=_api_response(roll))
    )
    result = await client.get_roll("o-abc123", "scr-abc")
    assert result["items"][0]["progress"]["value"] == 100


@respx.mock
@pytest.mark.asyncio
async def test_get_allowed_instance_types(client: SpotinstClient):
    types = [{"instanceTypes": ["c5.xlarge", "m5.large", "r5.large"]}]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/allowedInstanceTypes").mock(
        return_value=httpx.Response(200, json=_api_response(types))
    )
    result = await client.get_allowed_instance_types("o-abc123")
    assert "c5.xlarge" in result["items"][0]["instanceTypes"]


@respx.mock
@pytest.mark.asyncio
async def test_detach_instances(client: SpotinstClient):
    route = respx.put("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/detachInstances").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    await client.detach_instances("o-abc123", ["i-abc", "i-def"], should_terminate_instances=True)
    body = route.calls[0].request.content
    import json
    parsed = json.loads(body)
    assert parsed["instancesToDetach"] == ["i-abc", "i-def"]
    assert parsed["shouldTerminateInstances"] is True


@respx.mock
@pytest.mark.asyncio
async def test_update_vng(client: SpotinstClient):
    route = respx.put("https://api.spotinst.io/ocean/aws/k8s/launchSpec/ols-abc").mock(
        return_value=httpx.Response(200, json=_api_response([{"id": "ols-abc"}]))
    )
    await client.update_vng("ols-abc", {"resourceLimits": {"maxInstanceCount": 20}})
    import json
    parsed = json.loads(route.calls[0].request.content)
    assert parsed["launchSpec"]["resourceLimits"]["maxInstanceCount"] == 20


@respx.mock
@pytest.mark.asyncio
async def test_update_vng_azure(client: SpotinstClient):
    route = respx.put("https://api.spotinst.io/ocean/azure/np/virtualNodeGroup/vng-abc").mock(
        return_value=httpx.Response(200, json=_api_response([{"id": "vng-abc"}]))
    )
    await client.update_vng_azure("vng-abc", {"maxCount": 10})
    import json
    parsed = json.loads(route.calls[0].request.content)
    assert parsed["maxCount"] == 10


@respx.mock
@pytest.mark.asyncio
async def test_cluster_health_degraded(client: SpotinstClient):
    """Health should be DEGRADED when there are many errors."""
    logs = [{"message": f"Error {i}", "severity": "ERROR"} for i in range(10)]
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/nodes").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/log").mock(
        return_value=httpx.Response(200, json=_api_response(logs))
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/roll").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    result = await client.get_cluster_health("o-abc123")
    assert result["health"] == "DEGRADED"
    assert result["logs_24h"]["errors"] == 10


@respx.mock
@pytest.mark.asyncio
async def test_cluster_health_degraded_active_roll(client: SpotinstClient):
    """Health should be DEGRADED when there's an active roll."""
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/nodes").mock(
        return_value=httpx.Response(200, json=_api_response([{"instanceId": "i-1", "lifeCycle": "Spot"}]))
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/log").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/roll").mock(
        return_value=httpx.Response(200, json=_api_response([{"id": "scr-1", "status": "IN_PROGRESS"}]))
    )
    result = await client.get_cluster_health("o-abc123")
    assert result["health"] == "DEGRADED"
    assert result["rolls"]["active"] == 1


@respx.mock
@pytest.mark.asyncio
async def test_cost_trending_handles_400_gracefully(client: SpotinstClient):
    """Cost trending should return 'no data' for periods that 400."""
    call_count = 0

    def _side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=_api_response([{"result": {"total": 100}}]))
        return httpx.Response(400, json={"error": "no data"})

    respx.post(url__regex=r".*/aggregatedCosts").mock(side_effect=_side_effect)
    result = await client.get_cost_trending("o-abc123", periods=2, period_days=7)
    assert len(result) == 2
    has_data = sum(1 for r in result if r.get("data") is not None)
    has_none = sum(1 for r in result if r.get("note") is not None)
    assert has_data == 1
    assert has_none == 1


@respx.mock
@pytest.mark.asyncio
async def test_list_rolls_azure(client: SpotinstClient):
    rolls = [{"id": "scr-az1", "status": "COMPLETED"}]
    respx.get("https://api.spotinst.io/ocean/azure/np/cluster/o-az1/roll").mock(
        return_value=httpx.Response(200, json=_api_response(rolls))
    )
    result = await client.list_rolls("o-az1", cloud="azure")
    assert result["items"][0]["id"] == "scr-az1"


@respx.mock
@pytest.mark.asyncio
async def test_get_roll_azure(client: SpotinstClient):
    roll = [{"id": "scr-az1", "status": "IN_PROGRESS"}]
    respx.get("https://api.spotinst.io/ocean/azure/np/cluster/o-az1/roll/scr-az1").mock(
        return_value=httpx.Response(200, json=_api_response(roll))
    )
    result = await client.get_roll("o-az1", "scr-az1", cloud="azure")
    assert result["items"][0]["status"] == "IN_PROGRESS"


@respx.mock
@pytest.mark.asyncio
async def test_get_cluster_log_azure(client: SpotinstClient):
    logs = [{"message": "Azure scale up", "severity": "INFO"}]
    respx.get("https://api.spotinst.io/ocean/azure/np/cluster/o-az1/log").mock(
        return_value=httpx.Response(200, json=_api_response(logs))
    )
    result = await client.get_cluster_log("o-az1", "2026-03-20", "2026-03-20", cloud="azure")
    assert result["items"][0]["message"] == "Azure scale up"


@respx.mock
@pytest.mark.asyncio
async def test_initiate_roll_azure(client: SpotinstClient):
    respx.post("https://api.spotinst.io/ocean/azure/np/cluster/o-az1/roll").mock(
        return_value=httpx.Response(200, json=_api_response([{"id": "scr-az", "status": "IN_PROGRESS"}]))
    )
    result = await client.initiate_roll("o-az1", cloud="azure")
    assert result["items"][0]["status"] == "IN_PROGRESS"


@respx.mock
@pytest.mark.asyncio
async def test_initiate_roll_with_filters(client: SpotinstClient):
    """Verify launch_spec_ids and instance_ids are included in the request body."""
    route = respx.post("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc123/roll").mock(
        return_value=httpx.Response(200, json=_api_response([{"id": "scr-new"}]))
    )
    await client.initiate_roll(
        "o-abc123",
        launch_spec_ids=["ols-abc"],
        instance_ids=["i-123"],
    )
    import json
    body = json.loads(route.calls[0].request.content)
    assert body["roll"]["launchSpecIds"] == ["ols-abc"]
    assert body["roll"]["instanceIds"] == ["i-123"]


# --- Permission error handling ---


@respx.mock
@pytest.mark.asyncio
async def test_get_raises_permission_error_on_401(client: SpotinstClient):
    respx.get("https://api.spotinst.io/setup/account").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    with pytest.raises(PermissionError, match="Authentication failed"):
        await client.list_accounts()


@respx.mock
@pytest.mark.asyncio
async def test_get_raises_permission_error_on_403(client: SpotinstClient):
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    with pytest.raises(PermissionError, match="Access denied"):
        await client.list_clusters()


@respx.mock
@pytest.mark.asyncio
async def test_post_raises_permission_error_on_403(client: SpotinstClient):
    respx.post("https://api.spotinst.io/ocean/aws/k8s/cluster/o-abc/aggregatedCosts").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    with pytest.raises(PermissionError, match="Access denied"):
        await client.get_cluster_costs("o-abc", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")


@respx.mock
@pytest.mark.asyncio
async def test_put_raises_permission_error_on_403(client: SpotinstClient):
    respx.put("https://api.spotinst.io/ocean/aws/k8s/launchSpec/ols-abc").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    with pytest.raises(PermissionError, match="Access denied"):
        await client.update_vng("ols-abc", {"maxCount": 5})


# --- Capability probe ---


@respx.mock
@pytest.mark.asyncio
async def test_probe_capabilities_full_access(client: SpotinstClient):
    """Probe should report full access when all endpoints return 200."""
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json=_api_response([])))
    result = await client.probe_capabilities()
    assert result["token_valid"] is True
    assert len(result["denied"]) == 0
    assert "full access" in result["recommendation"]


@respx.mock
@pytest.mark.asyncio
async def test_probe_capabilities_partial_access(client: SpotinstClient):
    """Probe should report denied endpoints."""
    respx.get("https://api.spotinst.io/setup/account").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/cluster").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    respx.get("https://api.spotinst.io/ocean/azure/np/cluster").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    respx.get("https://api.spotinst.io/ocean/aws/k8s/launchSpec").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    respx.get("https://api.spotinst.io/ocean/azure/np/virtualNodeGroup").mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    respx.get("https://api.spotinst.io/aws/ec2/group").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    respx.get("https://api.spotinst.io/aws/ec2/managedInstance").mock(
        return_value=httpx.Response(200, json=_api_response([]))
    )
    result = await client.probe_capabilities()
    assert result["token_valid"] is True
    assert "azure_clusters" in result["denied"]
    assert "azure_vngs" in result["denied"]
    assert "lacks access" in result["recommendation"]


@respx.mock
@pytest.mark.asyncio
async def test_probe_capabilities_invalid_token(client: SpotinstClient):
    """Probe should detect invalid token."""
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    result = await client.probe_capabilities()
    assert result["token_valid"] is False
