"""Spot.io (Spotinst) API client."""

import asyncio
import os
from typing import Any

import httpx

BASE_URL = "https://api.spotinst.io"

# API path prefixes per cloud provider
AWS_CLUSTER = "/ocean/aws/k8s/cluster"
AWS_VNG = "/ocean/aws/k8s/launchSpec"
AZURE_CLUSTER = "/ocean/azure/np/cluster"
AZURE_VNG = "/ocean/azure/np/virtualNodeGroup"
# Azure costs oddly use the k8s path
AZURE_COSTS_CLUSTER = "/ocean/azure/k8s/cluster"


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

    async def _get_safe(
        self, path: str, params: dict[str, str] | None = None, account_id: str = ""
    ) -> Any | None:
        """Like _get but returns None on 400/404 instead of raising."""
        all_params = self._account_params(account_id)
        if params:
            all_params.update(params)
        resp = await self._client.get(path, params=all_params)
        if resp.status_code in (400, 404):
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    async def _post_safe(
        self, path: str, body: dict[str, Any], account_id: str = ""
    ) -> Any | None:
        """Like _post but returns None on 400/404 instead of raising."""
        resp = await self._client.post(
            path, params=self._account_params(account_id), json=body
        )
        if resp.status_code in (400, 404):
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    # --- Accounts ---

    async def list_accounts(self) -> Any:
        return await self._get("/setup/account")

    # --- All Clusters (cross-account, cross-cloud) ---

    async def list_all_clusters(self) -> list[dict[str, Any]]:
        """List clusters across all accounts and cloud providers."""
        accounts_resp = await self.list_accounts()
        accounts = accounts_resp.get("items", [])

        async def _get_clusters_for_account(
            acct: dict[str, Any],
        ) -> list[dict[str, Any]]:
            aid = acct["accountId"]
            provider = acct.get("cloudProvider", "")
            results = []

            if provider == "AWS":
                resp = await self._get_safe(AWS_CLUSTER, account_id=aid)
                if resp and resp.get("items"):
                    for c in resp["items"]:
                        c["_accountId"] = aid
                        c["_accountName"] = acct["name"]
                        c["_cloudProvider"] = "AWS"
                        results.append(c)

            elif provider == "AZURE":
                resp = await self._get_safe(AZURE_CLUSTER, account_id=aid)
                if resp and resp.get("items"):
                    for c in resp["items"]:
                        c["_accountId"] = aid
                        c["_accountName"] = acct["name"]
                        c["_cloudProvider"] = "AZURE"
                        results.append(c)

            return results

        tasks = [_get_clusters_for_account(a) for a in accounts]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        clusters = []
        for result in all_results:
            if isinstance(result, list):
                clusters.extend(result)
        return clusters

    # --- Ocean Clusters (AWS) ---

    async def list_clusters(self, account_id: str = "") -> Any:
        return await self._get(AWS_CLUSTER, account_id=account_id)

    async def get_cluster(self, cluster_id: str, account_id: str = "") -> Any:
        return await self._get(f"{AWS_CLUSTER}/{cluster_id}", account_id=account_id)

    # --- Ocean Clusters (Azure) ---

    async def list_clusters_azure(self, account_id: str = "") -> Any:
        return await self._get(AZURE_CLUSTER, account_id=account_id)

    async def get_cluster_azure(self, cluster_id: str, account_id: str = "") -> Any:
        return await self._get(
            f"{AZURE_CLUSTER}/{cluster_id}", account_id=account_id
        )

    # --- Ocean VNGs (AWS) ---

    async def list_vngs(
        self, ocean_id: str | None = None, account_id: str = ""
    ) -> Any:
        params = {}
        if ocean_id:
            params["oceanId"] = ocean_id
        return await self._get(AWS_VNG, params, account_id=account_id)

    async def get_vng(self, vng_id: str, account_id: str = "") -> Any:
        return await self._get(f"{AWS_VNG}/{vng_id}", account_id=account_id)

    # --- Ocean VNGs (Azure) ---

    async def list_vngs_azure(
        self, ocean_id: str | None = None, account_id: str = ""
    ) -> Any:
        params = {}
        if ocean_id:
            params["oceanId"] = ocean_id
        return await self._get(AZURE_VNG, params, account_id=account_id)

    async def get_vng_azure(self, vng_id: str, account_id: str = "") -> Any:
        return await self._get(f"{AZURE_VNG}/{vng_id}", account_id=account_id)

    # --- Elastigroups ---

    async def list_elastigroups(self, account_id: str = "") -> Any:
        return await self._get("/aws/ec2/group", account_id=account_id)

    async def get_elastigroup(self, group_id: str, account_id: str = "") -> Any:
        return await self._get(f"/aws/ec2/group/{group_id}", account_id=account_id)

    # --- Ocean Nodes ---

    async def get_cluster_nodes(
        self, cluster_id: str, account_id: str = "", cloud: str = "aws"
    ) -> Any:
        prefix = AZURE_CLUSTER if cloud == "azure" else AWS_CLUSTER
        return await self._get(
            f"{prefix}/{cluster_id}/nodes", account_id=account_id
        )

    # --- Ocean Costs ---

    async def get_cluster_costs(
        self,
        cluster_id: str,
        start_time: str,
        end_time: str,
        group_by: str = "namespace",
        account_id: str = "",
        cloud: str = "aws",
    ) -> Any:
        body = {
            "startTime": start_time,
            "endTime": end_time,
            "groupBy": group_by,
        }
        # Azure costs use /ocean/azure/k8s/ (not /np/)
        if cloud == "azure":
            prefix = AZURE_COSTS_CLUSTER
        else:
            prefix = AWS_CLUSTER
        return await self._post(
            f"{prefix}/{cluster_id}/aggregatedCosts",
            body,
            account_id=account_id,
        )

    # --- Ocean Right-Sizing Suggestions (AWS only) ---

    async def get_right_sizing(
        self, cluster_id: str, namespace: str = "", account_id: str = ""
    ) -> Any:
        params = {}
        if namespace:
            params["namespace"] = namespace
        return await self._get(
            f"{AWS_CLUSTER}/{cluster_id}/rightSizing/resourceSuggestion",
            params,
            account_id=account_id,
        )

    # --- Ocean Rolls ---

    async def list_rolls(
        self, cluster_id: str, account_id: str = "", cloud: str = "aws"
    ) -> Any:
        prefix = AZURE_CLUSTER if cloud == "azure" else AWS_CLUSTER
        return await self._get(
            f"{prefix}/{cluster_id}/roll", account_id=account_id
        )

    async def get_roll(
        self,
        cluster_id: str,
        roll_id: str,
        account_id: str = "",
        cloud: str = "aws",
    ) -> Any:
        prefix = AZURE_CLUSTER if cloud == "azure" else AWS_CLUSTER
        return await self._get(
            f"{prefix}/{cluster_id}/roll/{roll_id}",
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
        cloud: str = "aws",
    ) -> Any:
        params = {
            "fromDate": from_date,
            "toDate": to_date,
            "severity": severity,
            "limit": str(limit),
        }
        prefix = AZURE_CLUSTER if cloud == "azure" else AWS_CLUSTER
        return await self._get(
            f"{prefix}/{cluster_id}/log",
            params,
            account_id=account_id,
        )

    # --- Allowed Instance Types (AWS only) ---

    async def get_allowed_instance_types(
        self, cluster_id: str, account_id: str = ""
    ) -> Any:
        return await self._get(
            f"{AWS_CLUSTER}/{cluster_id}/allowedInstanceTypes",
            account_id=account_id,
        )

    async def close(self) -> None:
        await self._client.aclose()
