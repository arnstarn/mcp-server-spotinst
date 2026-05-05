"""Live AWS Ocean VNG integration matrix.

Exercises every v0.7.0 write tool against a throwaway VNG so we catch
regressions before cutting a release. See conftest.py for opt-in envvars.
"""

import base64
import json
import os

import pytest

from mcp_server_spotinst.server import (
    _get_client,
    create_vng,
    delete_vng,
    update_vng,
)
from mcp_server_spotinst.spotinst_client import SpotinstClient

from .conftest import _safe_spec, make_sandbox_name


def _enabled() -> bool:
    return os.environ.get("SPOTINST_RUN_INTEGRATION") == "1"


pytestmark = [
    pytest.mark.skipif(not _enabled(), reason="set SPOTINST_RUN_INTEGRATION=1 to run"),
    pytest.mark.asyncio,
]


async def test_create_vng_rejects_ocean_id_inside_spec(integration_config):
    """If someone accidentally puts oceanId in spec_json, surface it loudly."""
    spec = {"oceanId": integration_config["ocean_id"], "name": "bad"}
    result = await create_vng(
        ocean_id=integration_config["ocean_id"],
        spec_json=json.dumps(spec),
        confirm=True,
        account_id=integration_config["account_id"],
    )
    assert "ERROR" in result or "oceanId" in result


async def test_create_vng_safety_preview_without_confirm(integration_config):
    """confirm=False must never hit the API."""
    name = make_sandbox_name()
    result = await create_vng(
        ocean_id=integration_config["ocean_id"],
        spec_json=json.dumps({"name": name, "imageId": integration_config["ami_id"]}),
        confirm=False,
        account_id=integration_config["account_id"],
    )
    assert "SAFETY" in result
    assert name in result


async def test_update_vng_plaintext_userdata_auto_encodes(ephemeral_vng, integration_config):
    plaintext = "#!/bin/bash\necho integration-test-plain\n"
    result = await update_vng(
        vng_id=ephemeral_vng,
        updates_json=json.dumps({"userData": plaintext}),
        confirm=True,
        account_id=integration_config["account_id"],
        encode_user_data=True,
    )
    parsed = json.loads(result)
    assert "put_result" in parsed
    assert "_readback_mismatch" not in parsed, parsed.get("_readback_mismatch")


async def test_update_vng_already_base64_passthrough(ephemeral_vng, integration_config):
    plaintext = "#!/bin/bash\necho integration-test-b64\n"
    encoded = base64.b64encode(plaintext.encode()).decode()
    result = await update_vng(
        vng_id=ephemeral_vng,
        updates_json=json.dumps({"userData": encoded}),
        confirm=True,
        account_id=integration_config["account_id"],
        encode_user_data=False,
    )
    parsed = json.loads(result)
    assert "_readback_mismatch" not in parsed, parsed.get("_readback_mismatch")


async def test_update_vng_auto_apply_tags(ephemeral_vng, integration_config):
    """autoApplyTags=true should land new labels without a roll."""
    result = await update_vng(
        vng_id=ephemeral_vng,
        updates_json=json.dumps(
            {"labels": [{"key": "sandbox-test", "value": "tagged"}]}
        ),
        confirm=True,
        account_id=integration_config["account_id"],
        auto_apply_tags=True,
    )
    parsed = json.loads(result)
    assert "put_result" in parsed


async def test_update_vng_missing_account_id_raises():
    """Bypass the tool wrapper's env fallback and assert the client raises."""
    client = SpotinstClient(token="dummy", account_id="")
    with pytest.raises(ValueError, match="accountId is required"):
        await client.update_vng(
            vng_id="ols-nonexistent",
            updates={"resourceLimits": {"maxInstanceCount": 1}},
            account_id="",
        )


async def test_probe_token_capabilities_reports_write_access(integration_config):
    """End-to-end: token must report write access for this suite to be meaningful."""
    caps = await _get_client().probe_capabilities()
    assert caps.get("write_access") is True, caps


async def test_delete_vng_safety_preview(integration_config, integration_client):
    """Create a throwaway and verify confirm=False does not delete it."""
    created = await integration_client.create_vng(
        ocean_id=integration_config["ocean_id"],
        spec=_safe_spec(integration_config["ami_id"], make_sandbox_name()),
        account_id=integration_config["account_id"],
        initial_nodes=0,
    )
    vng_id = created["items"][0]["id"]
    try:
        preview = await delete_vng(
            vng_id=vng_id,
            confirm=False,
            account_id=integration_config["account_id"],
        )
        assert "SAFETY" in preview
        still_there = await integration_client.get_vng(vng_id, integration_config["account_id"])
        assert still_there.get("items"), "VNG was deleted despite confirm=False"
    finally:
        await integration_client.delete_vng(
            vng_id=vng_id,
            account_id=integration_config["account_id"],
            delete_nodes=True,
        )
