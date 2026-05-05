"""Integration-test fixtures that talk to a live Spot.io tenant.

Skipped by default. Opt in with:

    SPOTINST_RUN_INTEGRATION=1 \
    SPOTINST_TOKEN=... \
    SPOTINST_ACCOUNT_ID=act-... \
    SPOTINST_TEST_OCEAN_ID=o-... \
    SPOTINST_TEST_AMI_ID=ami-... \
    pytest tests/integration

The fixture creates an ephemeral VNG under the target Ocean cluster and tears
it down after the test session.

Isolation guarantees:
- `initialNodes=0`, `minInstanceCount=0`: Ocean never pre-launches a node.
- `autoScale.headrooms=[]`: the autoscaler never pre-warms capacity here.
- `maxInstanceCount=1` + `t3.small`: blast radius is capped at one small
  instance if something unexpectedly tries to scale (~$0.02/hr).
- `NoSchedule` + `NoExecute` taints with a unique key: no real workload
  tolerates this; anything that somehow lands is evicted immediately.
- Session-scoped sweep at teardown cleans up any VNG whose name starts with
  `TEST_VNG_NAME_PREFIX`, in case a mid-test failure left an orphan.
"""

import os
import uuid

import pytest
import pytest_asyncio

from mcp_server_spotinst.spotinst_client import SpotinstClient

TEST_VNG_NAME_PREFIX = "sandbox-test-"
TEST_VNG_TAINT_KEY = "sandbox-test"
TEST_VNG_TAINT_VALUE = "true"


def _enabled() -> bool:
    return os.environ.get("SPOTINST_RUN_INTEGRATION") == "1"


pytestmark = pytest.mark.skipif(
    not _enabled(), reason="set SPOTINST_RUN_INTEGRATION=1 to run"
)


@pytest.fixture(scope="session")
def integration_config() -> dict:
    required = [
        "SPOTINST_TOKEN",
        "SPOTINST_ACCOUNT_ID",
        "SPOTINST_TEST_OCEAN_ID",
        "SPOTINST_TEST_AMI_ID",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        pytest.skip(f"missing env vars: {', '.join(missing)}")
    return {
        "account_id": os.environ["SPOTINST_ACCOUNT_ID"],
        "ocean_id": os.environ["SPOTINST_TEST_OCEAN_ID"],
        "ami_id": os.environ["SPOTINST_TEST_AMI_ID"],
    }


def _safe_spec(ami_id: str, name: str) -> dict:
    """Spec that guarantees no node ever launches and no pod ever lands."""
    return {
        "name": name,
        "imageId": ami_id,
        "instanceTypes": ["t3.small"],
        "labels": [{"key": TEST_VNG_TAINT_KEY, "value": TEST_VNG_TAINT_VALUE}],
        "taints": [
            {"key": TEST_VNG_TAINT_KEY, "value": TEST_VNG_TAINT_VALUE, "effect": "NoSchedule"},
            {"key": TEST_VNG_TAINT_KEY, "value": TEST_VNG_TAINT_VALUE, "effect": "NoExecute"},
        ],
        "resourceLimits": {"maxInstanceCount": 1, "minInstanceCount": 0},
        "autoScale": {"headrooms": []},
    }


def make_sandbox_name() -> str:
    return f"{TEST_VNG_NAME_PREFIX}{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture(scope="session")
async def integration_client():
    client = SpotinstClient()
    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def session_sweep(integration_config, integration_client):
    """Belt-and-suspenders: after the session, delete any lingering VNG whose
    name starts with our prefix. Catches orphans from crashes inside a test."""
    yield
    try:
        listing = await integration_client.list_vngs(integration_config["account_id"])
    except Exception:
        return
    items = listing.get("items") if isinstance(listing, dict) else listing
    if not isinstance(items, list):
        return
    for item in items:
        name = (item or {}).get("name", "")
        vng_id = (item or {}).get("id")
        if name.startswith(TEST_VNG_NAME_PREFIX) and vng_id:
            try:
                await integration_client.delete_vng(
                    vng_id=vng_id,
                    account_id=integration_config["account_id"],
                    delete_nodes=True,
                )
            except Exception:
                pass  # best-effort cleanup


@pytest_asyncio.fixture()
async def ephemeral_vng(integration_config, integration_client):
    """Create a sandbox VNG, yield its id, then delete it."""
    spec = _safe_spec(integration_config["ami_id"], make_sandbox_name())
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
