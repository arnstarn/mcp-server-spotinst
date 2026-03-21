"""Tests for the Spotinst API client using mocked HTTP responses."""

import json

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
