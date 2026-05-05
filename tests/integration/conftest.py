"""Integration-test fixtures that talk to a live Spot.io tenant.

Skipped by default. Opt in with:

    SPOTINST_RUN_INTEGRATION=1 \
    SPOTINST_TOKEN=... \
    SPOTINST_ACCOUNT_ID=act-... \
    SPOTINST_TEST_OCEAN_ID=o-... \
    SPOTINST_TEST_AMI_ID=ami-... \
    pytest tests/integration

The fixture creates an ephemeral VNG under the target Ocean cluster and tears
it down after the test session. The VNG is harmless: `initialNodes=0`, a
unique name, taint so nothing real ever schedules on it, and an instance-type
list that's valid but never matched because of the taint.
"""

import os
import uuid

import pytest
import pytest_asyncio

from mcp_server_spotinst.spotinst_client import SpotinstClient


def _enabled() -> bool:
    return os.environ.get("SPOTINST_RUN_INTEGRATION") == "1"


pytestmark = pytest.mark.skipif(
    not _enabled(), reason="set SPOTINST_RUN_INTEGRATION=1 to run"
)


@pytest.fixture(scope="session")
def integration_config() -> dict:
    required = ["SPOTINST_TOKEN", "SPOTINST_ACCOUNT_ID", "SPOTINST_TEST_OCEAN_ID", "SPOTINST_TEST_AMI_ID"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        pytest.skip(f"missing env vars: {', '.join(missing)}")
    return {
        "account_id": os.environ["SPOTINST_ACCOUNT_ID"],
        "ocean_id": os.environ["SPOTINST_TEST_OCEAN_ID"],
        "ami_id": os.environ["SPOTINST_TEST_AMI_ID"],
    }


@pytest_asyncio.fixture(scope="session")
async def integration_client():
    client = SpotinstClient()
    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture()
async def ephemeral_vng(integration_config, integration_client):
    """Create a minimal VNG, yield its id, then delete it."""
    name = f"mcp-integ-{uuid.uuid4().hex[:8]}"
    spec = {
        "name": name,
        "imageId": integration_config["ami_id"],
        "instanceTypes": ["t3.small"],
        "labels": [{"key": "mcp-integ", "value": "true"}],
        "taints": [
            {"key": "mcp-integ", "value": "true", "effect": "NoSchedule"}
        ],
        "resourceLimits": {"maxInstanceCount": 1, "minInstanceCount": 0},
    }
    created = await integration_client.create_vng(
        ocean_id=integration_config["ocean_id"],
        spec=spec,
        account_id=integration_config["account_id"],
        initial_nodes=0,
    )
    items = created.get("items") if isinstance(created, dict) else None
    assert items, f"create_vng returned no items: {created}"
    vng_id = items[0]["id"]
    try:
        yield vng_id
    finally:
        try:
            await integration_client.delete_vng(
                vng_id=vng_id,
                account_id=integration_config["account_id"],
                delete_nodes=True,
                force_delete=False,
            )
        except Exception as e:
            pytest.fail(f"teardown: delete_vng failed for {vng_id}: {e}")
