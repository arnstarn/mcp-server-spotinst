# mcp-server-spotinst

MCP server for the [Spot.io (Spotinst)](https://spot.io/) API. Exposes Ocean clusters, VNGs, Elastigroups, costs, right-sizing, rolls, and logs as MCP tools. All tools support multi-account access.

## Tools

| Tool | Description |
|------|-------------|
| `list_accounts` | List all Spotinst accounts accessible with the current token |
| `list_clusters` | List all Ocean K8s clusters |
| `get_cluster` | Get details of a specific Ocean cluster |
| `list_vngs` | List Virtual Node Groups (launch specs) |
| `get_vng` | Get VNG details |
| `list_elastigroups` | List all Elastigroups |
| `get_elastigroup` | Get Elastigroup details |
| `get_cluster_nodes` | List nodes in an Ocean cluster |
| `get_cluster_costs` | Get aggregated cost breakdown by namespace or resource |
| `get_right_sizing` | Get right-sizing resource suggestions for workloads |
| `list_rolls` | List deployment rolls for an Ocean cluster |
| `get_roll` | Get details of a specific roll |
| `get_cluster_log` | Get scaling and activity log events |
| `get_allowed_instance_types` | Get allowed EC2 instance types for a cluster |

All tools accept an optional `account_id` parameter to query a different Spotinst account than the default.

## Setup

### Environment Variables

```bash
export SPOTINST_TOKEN="your-spotinst-api-token"
export SPOTINST_ACCOUNT_ID="act-xxxxxxxx"
```

### Install with pip

```bash
pip install mcp-server-spotinst
```

### Install with uvx (no install needed)

```bash
uvx mcp-server-spotinst
```

### Claude Code Config

Add to `~/.mcp.json`:

```json
{
  "mcpServers": {
    "spotinst": {
      "command": "uvx",
      "args": ["mcp-server-spotinst"],
      "env": {
        "SPOTINST_TOKEN": "your-token",
        "SPOTINST_ACCOUNT_ID": "act-xxxxxxxx"
      }
    }
  }
}
```

### Run Standalone

```bash
mcp-server-spotinst
```

## Multi-Account Usage

Your personal API token can access multiple Spotinst accounts. Use `list_accounts` to see all available accounts, then pass `account_id` to any tool:

```
list_clusters(account_id="act-be5e7ffe")
```

## API Reference

Uses the [Spot.io REST API](https://docs.spot.io/api/) at `https://api.spotinst.io`.
