"""Spot.io (Spotinst) API client."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
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

    def _check_permission(self, resp: httpx.Response, path: str) -> None:
        """Raise a clear error on 401/403 instead of a generic HTTP error."""
        if resp.status_code == 401:
            raise PermissionError(
                f"Authentication failed for {path}. "
                "Your SPOTINST_TOKEN may be invalid or expired."
            )
        if resp.status_code == 403:
            raise PermissionError(
                f"Access denied for {path}. "
                "Your token does not have permission for this operation. "
                "Check your token's policy/role in the Spot.io console."
            )

    async def _get(
        self, path: str, params: dict[str, str] | None = None, account_id: str = ""
    ) -> Any:
        all_params = self._account_params(account_id)
        if params:
            all_params.update(params)
        resp = await self._client.get(path, params=all_params)
        self._check_permission(resp, path)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    async def _post(
        self, path: str, body: dict[str, Any], account_id: str = ""
    ) -> Any:
        resp = await self._client.post(
            path, params=self._account_params(account_id), json=body
        )
        self._check_permission(resp, path)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    async def _put(
        self, path: str, body: dict[str, Any], account_id: str = ""
    ) -> Any:
        resp = await self._client.put(
            path, params=self._account_params(account_id), json=body
        )
        self._check_permission(resp, path)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", data)

    async def _delete(
        self, path: str, account_id: str = "", body: dict[str, Any] | None = None
    ) -> Any:
        resp = await self._client.request(
            "DELETE",
            path,
            params=self._account_params(account_id),
            json=body,
        )
        self._check_permission(resp, path)
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

    # --- Token Capabilities ---

    async def probe_capabilities(self) -> dict[str, Any]:
        """Probe which API endpoints the current token can access."""
        probes = {
            "accounts": "/setup/account",
            "aws_clusters": AWS_CLUSTER,
            "azure_clusters": AZURE_CLUSTER,
            "aws_vngs": AWS_VNG,
            "azure_vngs": AZURE_VNG,
            "elastigroups": "/aws/ec2/group",
            "stateful_nodes": "/aws/ec2/managedInstance",
            "stateful_nodes_azure": "/azure/compute/statefulNode",
        }

        results: dict[str, Any] = {}
        for name, path in probes.items():
            resp = await self._client.get(path, params=self._account_params())
            if resp.status_code == 200:
                results[name] = "ok"
            elif resp.status_code in (401, 403):
                results[name] = "denied"
            elif resp.status_code == 400:
                # 400 usually means the endpoint exists but needs different params (e.g. wrong cloud)
                results[name] = "ok (cloud mismatch or no resources)"
            else:
                results[name] = f"error ({resp.status_code})"

        # Derive summary
        accessible = [k for k, v in results.items() if v.startswith("ok")]
        denied = [k for k, v in results.items() if v == "denied"]

        return {
            "token_valid": results.get("accounts") != "denied",
            "accessible": accessible,
            "denied": denied,
            "details": results,
            "recommendation": (
                "Token has full access." if not denied
                else f"Token lacks access to: {', '.join(denied)}. Some tools will not work."
            ),
        }

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

    # --- Ocean Right-Sizing Suggestions ---

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

    async def get_right_sizing_azure(
        self, cluster_id: str, namespace: str = "", account_id: str = ""
    ) -> Any:
        body: dict[str, Any] = {}
        if namespace:
            body["namespace"] = namespace
        return await self._post(
            f"{AZURE_CLUSTER}/{cluster_id}/rightSizing/suggestion",
            body,
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

    # ===================================================================
    # WRITE OPERATIONS (destructive — use with caution)
    # ===================================================================

    # --- Initiate Roll ---

    async def initiate_roll(
        self,
        cluster_id: str,
        batch_size_percentage: int = 20,
        batch_min_healthy_percentage: int = 50,
        respect_pdb: bool = True,
        launch_spec_ids: list[str] | None = None,
        instance_ids: list[str] | None = None,
        account_id: str = "",
        cloud: str = "aws",
    ) -> Any:
        prefix = AZURE_CLUSTER if cloud == "azure" else AWS_CLUSTER
        body: dict[str, Any] = {
            "roll": {
                "batchSizePercentage": batch_size_percentage,
                "batchMinHealthyPercentage": batch_min_healthy_percentage,
                "respectPdb": respect_pdb,
            }
        }
        if launch_spec_ids:
            body["roll"]["launchSpecIds"] = launch_spec_ids
        if instance_ids:
            body["roll"]["instanceIds"] = instance_ids
        return await self._post(
            f"{prefix}/{cluster_id}/roll", body, account_id=account_id
        )

    # --- Detach Instances ---

    async def detach_instances(
        self,
        cluster_id: str,
        instance_ids: list[str],
        should_decrement_target_capacity: bool = True,
        should_terminate_instances: bool = True,
        account_id: str = "",
    ) -> Any:
        body = {
            "instancesToDetach": instance_ids,
            "shouldDecrementTargetCapacity": should_decrement_target_capacity,
            "shouldTerminateInstances": should_terminate_instances,
        }
        return await self._put(
            f"{AWS_CLUSTER}/{cluster_id}/detachInstances",
            body,
            account_id=account_id,
        )

    # --- Update VNG ---

    async def update_vng(
        self,
        vng_id: str,
        updates: dict[str, Any],
        account_id: str = "",
    ) -> Any:
        body = {"launchSpec": updates}
        return await self._put(
            f"{AWS_VNG}/{vng_id}", body, account_id=account_id
        )

    async def update_vng_azure(
        self,
        vng_id: str,
        updates: dict[str, Any],
        account_id: str = "",
    ) -> Any:
        return await self._put(
            f"{AZURE_VNG}/{vng_id}", updates, account_id=account_id
        )

    # --- Stateful Nodes (AWS Managed Instances) ---

    async def list_stateful_nodes(self, account_id: str = "") -> Any:
        return await self._get("/aws/ec2/managedInstance", account_id=account_id)

    async def get_stateful_node(self, node_id: str, account_id: str = "") -> Any:
        return await self._get(f"/aws/ec2/managedInstance/{node_id}", account_id=account_id)

    # --- Stateful Nodes (Azure) ---

    async def list_stateful_nodes_azure(self, account_id: str = "") -> Any:
        return await self._get("/azure/compute/statefulNode", account_id=account_id)

    async def get_stateful_node_azure(self, node_id: str, account_id: str = "") -> Any:
        return await self._get(f"/azure/compute/statefulNode/{node_id}", account_id=account_id)

    # --- Scheduling (Ocean Cluster Scheduling Config) ---

    async def get_cluster_scheduling(self, cluster_id: str, account_id: str = "", cloud: str = "aws") -> Any:
        """Get the full cluster config and extract scheduling/auto-scaler settings."""
        prefix = AZURE_CLUSTER if cloud == "azure" else AWS_CLUSTER
        return await self._get(f"{prefix}/{cluster_id}", account_id=account_id)

    # --- Cost Trending ---

    async def get_cost_trending(
        self,
        cluster_id: str,
        periods: int = 4,
        period_days: int = 7,
        group_by: str = "namespace",
        account_id: str = "",
        cloud: str = "aws",
    ) -> list[dict[str, Any]]:
        """Get costs for multiple consecutive time periods for trending analysis."""
        now = datetime.now(timezone.utc)

        async def _fetch_period(i: int) -> dict[str, Any]:
            end = now - timedelta(days=i * period_days)
            start = end - timedelta(days=period_days)
            start_str = start.strftime("%Y-%m-%dT00:00:00Z")
            end_str = end.strftime("%Y-%m-%dT00:00:00Z")
            period_label = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
            body = {"startTime": start_str, "endTime": end_str, "groupBy": group_by}
            if cloud == "azure":
                prefix = AZURE_COSTS_CLUSTER
            else:
                prefix = AWS_CLUSTER
            resp = await self._post_safe(
                f"{prefix}/{cluster_id}/aggregatedCosts", body, account_id=account_id
            )
            base = {"period": period_label, "start": start_str, "end": end_str}
            if resp is None:
                return {**base, "data": None, "note": "no data available for this period"}
            return {**base, "data": resp}

        # Run sequentially — Spot.io costs API doesn't handle concurrent requests well
        results: list[dict[str, Any]] = []
        for i in range(periods):
            results.append(await _fetch_period(i))
        return sorted(results, key=lambda x: x.get("start", ""))

    # --- Spot Savings ---

    async def get_cluster_summary(self, cluster_id: str, account_id: str = "", cloud: str = "aws") -> Any:
        """Get cluster summary including savings data from costs endpoint."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        return await self.get_cluster_costs(
            cluster_id,
            start.strftime("%Y-%m-%dT00:00:00Z"),
            now.strftime("%Y-%m-%dT00:00:00Z"),
            "namespace",
            account_id,
            cloud,
        )

    # --- Cluster Health ---

    async def get_cluster_health(self, cluster_id: str, account_id: str = "", cloud: str = "aws") -> dict[str, Any]:
        """Composite health check: nodes + recent logs + rolls."""
        prefix = AZURE_CLUSTER if cloud == "azure" else AWS_CLUSTER
        now = datetime.now(timezone.utc)
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        nodes_task = self._get_safe(f"{prefix}/{cluster_id}/nodes", account_id=account_id)
        logs_task = self._get_safe(
            f"{prefix}/{cluster_id}/log",
            params={"fromDate": yesterday, "toDate": today, "severity": "ALL", "limit": "50"},
            account_id=account_id,
        )
        rolls_task = self._get_safe(f"{prefix}/{cluster_id}/roll", account_id=account_id)

        nodes_resp, logs_resp, rolls_resp = await asyncio.gather(nodes_task, logs_task, rolls_task)

        # Analyze nodes
        nodes = (nodes_resp or {}).get("items", [])
        total_nodes = len(nodes)
        lifecycle_counts: dict[str, int] = {}
        for n in nodes:
            lc = n.get("lifeCycle", n.get("vmSize", "unknown"))
            lifecycle_counts[lc] = lifecycle_counts.get(lc, 0) + 1

        # Analyze logs
        logs = (logs_resp or {}).get("items", [])
        error_count = sum(1 for entry in logs if entry.get("severity") == "ERROR")
        warn_count = sum(1 for entry in logs if entry.get("severity") == "WARN")
        recent_errors = [entry for entry in logs if entry.get("severity") == "ERROR"][:5]

        # Analyze rolls
        rolls = (rolls_resp or {}).get("items", [])
        active_rolls = [r for r in rolls if r.get("status") in ("IN_PROGRESS", "PENDING")]

        return {
            "cluster_id": cluster_id,
            "cloud": cloud,
            "nodes": {
                "total": total_nodes,
                "by_lifecycle": lifecycle_counts,
            },
            "logs_24h": {
                "total": len(logs),
                "errors": error_count,
                "warnings": warn_count,
                "recent_errors": recent_errors,
            },
            "rolls": {
                "total": len(rolls),
                "active": len(active_rolls),
                "active_details": active_rolls,
            },
            "health": "DEGRADED" if error_count > 5 or active_rolls else "OK",
        }

    async def close(self) -> None:
        await self._client.aclose()
