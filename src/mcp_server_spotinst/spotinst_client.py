"""Spot.io (Spotinst) API client."""

import os
from typing import Any

import httpx

BASE_URL = "https://api.spotinst.io"


class SpotinstClient:
    def __init__(
        self,
        token: str | None = None,
        account_id: str | None = None,
    ):
        self.token = token or os.environ["SPOTINST_TOKEN"]
        self.account_id = account_id or os.environ.get("SPOTINST_ACCOUNT_ID", "")
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _account_params(self) -> dict[str, str]:
        return {"accountId": self.account_id} if self.account_id else {}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        all_params = self._account_params()
        if params:
            all_params.update(params)
        resp = await self._client.get(path, params=all_params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    async def _post(self, path: str, body: dict[str, Any]) -> Any:
        resp = await self._client.post(
            path, params=self._account_params(), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    # --- Ocean Clusters ---

    async def list_clusters(self) -> Any:
        return await self._get("/ocean/aws/k8s/cluster")

    async def get_cluster(self, cluster_id: str) -> Any:
        return await self._get(f"/ocean/aws/k8s/cluster/{cluster_id}")

    # --- Ocean Launch Specs (VNGs) ---

    async def list_vngs(self, ocean_id: str | None = None) -> Any:
        params = {}
        if ocean_id:
            params["oceanId"] = ocean_id
        return await self._get("/ocean/aws/k8s/launchSpec", params)

    async def get_vng(self, vng_id: str) -> Any:
        return await self._get(f"/ocean/aws/k8s/launchSpec/{vng_id}")

    # --- Elastigroups ---

    async def list_elastigroups(self) -> Any:
        return await self._get("/aws/ec2/group")

    async def get_elastigroup(self, group_id: str) -> Any:
        return await self._get(f"/aws/ec2/group/{group_id}")

    # --- Ocean Nodes ---

    async def get_cluster_nodes(self, cluster_id: str) -> Any:
        return await self._get(f"/ocean/aws/k8s/cluster/{cluster_id}/nodes")

    # --- Ocean Costs ---

    async def get_cluster_costs(
        self,
        cluster_id: str,
        start_time: str,
        end_time: str,
        group_by: str = "namespace",
    ) -> Any:
        body = {
            "startTime": start_time,
            "endTime": end_time,
            "groupBy": group_by,
        }
        return await self._post(
            f"/ocean/aws/k8s/cluster/{cluster_id}/aggregatedCosts", body
        )

    # --- Ocean Right-Sizing Suggestions ---

    async def get_right_sizing(self, cluster_id: str, namespace: str = "") -> Any:
        params = {}
        if namespace:
            params["namespace"] = namespace
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}/rightSizing/resourceSuggestion",
            params,
        )

    # --- Accounts ---

    async def list_accounts(self) -> Any:
        return await self._get("/setup/account")

    async def close(self) -> None:
        await self._client.aclose()
