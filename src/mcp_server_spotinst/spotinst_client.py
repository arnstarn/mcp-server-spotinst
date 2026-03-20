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

    def _account_params(self, account_id: str = "") -> dict[str, str]:
        aid = account_id or self.account_id
        return {"accountId": aid} if aid else {}

    async def _get(
        self, path: str, params: dict[str, str] | None = None, account_id: str = ""
    ) -> Any:
        all_params = self._account_params(account_id)
        if params:
            all_params.update(params)
        resp = await self._client.get(path, params=all_params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    async def _post(
        self, path: str, body: dict[str, Any], account_id: str = ""
    ) -> Any:
        resp = await self._client.post(
            path, params=self._account_params(account_id), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    # --- Accounts ---

    async def list_accounts(self) -> Any:
        return await self._get("/setup/account")

    # --- Ocean Clusters ---

    async def list_clusters(self, account_id: str = "") -> Any:
        return await self._get("/ocean/aws/k8s/cluster", account_id=account_id)

    async def get_cluster(self, cluster_id: str, account_id: str = "") -> Any:
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}", account_id=account_id
        )

    # --- Ocean Launch Specs (VNGs) ---

    async def list_vngs(
        self, ocean_id: str | None = None, account_id: str = ""
    ) -> Any:
        params = {}
        if ocean_id:
            params["oceanId"] = ocean_id
        return await self._get(
            "/ocean/aws/k8s/launchSpec", params, account_id=account_id
        )

    async def get_vng(self, vng_id: str, account_id: str = "") -> Any:
        return await self._get(
            f"/ocean/aws/k8s/launchSpec/{vng_id}", account_id=account_id
        )

    # --- Elastigroups ---

    async def list_elastigroups(self, account_id: str = "") -> Any:
        return await self._get("/aws/ec2/group", account_id=account_id)

    async def get_elastigroup(self, group_id: str, account_id: str = "") -> Any:
        return await self._get(f"/aws/ec2/group/{group_id}", account_id=account_id)

    # --- Ocean Nodes ---

    async def get_cluster_nodes(self, cluster_id: str, account_id: str = "") -> Any:
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}/nodes", account_id=account_id
        )

    # --- Ocean Costs ---

    async def get_cluster_costs(
        self,
        cluster_id: str,
        start_time: str,
        end_time: str,
        group_by: str = "namespace",
        account_id: str = "",
    ) -> Any:
        body = {
            "startTime": start_time,
            "endTime": end_time,
            "groupBy": group_by,
        }
        return await self._post(
            f"/ocean/aws/k8s/cluster/{cluster_id}/aggregatedCosts",
            body,
            account_id=account_id,
        )

    # --- Ocean Right-Sizing Suggestions ---

    async def get_right_sizing(
        self, cluster_id: str, namespace: str = "", account_id: str = ""
    ) -> Any:
        params = {}
        if namespace:
            params["namespace"] = namespace
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}/rightSizing/resourceSuggestion",
            params,
            account_id=account_id,
        )

    # --- Ocean Rolls ---

    async def list_rolls(self, cluster_id: str, account_id: str = "") -> Any:
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}/roll", account_id=account_id
        )

    async def get_roll(
        self, cluster_id: str, roll_id: str, account_id: str = ""
    ) -> Any:
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}/roll/{roll_id}",
            account_id=account_id,
        )

    # --- Ocean Cluster Log ---

    async def get_cluster_log(
        self,
        cluster_id: str,
        from_date: str,
        to_date: str,
        severity: str = "ALL",
        limit: int = 500,
        account_id: str = "",
    ) -> Any:
        params = {
            "fromDate": from_date,
            "toDate": to_date,
            "severity": severity,
            "limit": str(limit),
        }
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}/log",
            params,
            account_id=account_id,
        )

    # --- Allowed Instance Types ---

    async def get_allowed_instance_types(
        self, cluster_id: str, account_id: str = ""
    ) -> Any:
        return await self._get(
            f"/ocean/aws/k8s/cluster/{cluster_id}/allowedInstanceTypes",
            account_id=account_id,
        )

    async def close(self) -> None:
        await self._client.aclose()
