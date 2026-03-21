# mcp-server-spotinst

MCP server for the [Spot.io (Spotinst)](https://spot.io/) API. Supports both AWS and Azure Ocean clusters with multi-account access.

## Tools (19)

### Cross-Account

| Tool | Description |
|------|-------------|
| `list_accounts` | List all Spotinst accounts accessible with the current token |
| `list_all_clusters` | List ALL clusters across ALL accounts and clouds (AWS + Azure) |

### AWS Ocean

| Tool | Description |
|------|-------------|
| `list_clusters` | List AWS Ocean K8s clusters |
| `get_cluster` | Get AWS Ocean cluster details |
| `list_vngs` | List AWS Virtual Node Groups (launch specs) |
| `get_vng` | Get AWS VNG details |
| `list_elastigroups` | List all Elastigroups |
| `get_elastigroup` | Get Elastigroup details |
| `get_allowed_instance_types` | Get allowed EC2 instance types |
| `get_right_sizing` | Get right-sizing resource suggestions (AWS only) |

### Azure Ocean

| Tool | Description |
|------|-------------|
| `list_clusters_azure` | List Azure Ocean clusters |
| `get_cluster_azure` | Get Azure Ocean cluster details |
| `list_vngs_azure` | List Azure Virtual Node Groups |
| `get_vng_azure` | Get Azure VNG details |

### Both Clouds (pass `cloud="azure"` for Azure)

| Tool | Description |
|------|-------------|
| `get_cluster_nodes` | List nodes in an Ocean cluster |
| `get_cluster_costs` | Get aggregated cost breakdown by namespace or resource |
| `list_rolls` | List deployment rolls |
| `get_roll` | Get roll details |
| `get_cluster_log` | Get scaling and activity log events |

All tools accept an optional `account_id` parameter to query any account.

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
get_cluster_nodes("o-390ef886", account_id="act-9785011e", cloud="azure")
```

Or use `list_all_clusters` for a single-call inventory across everything.

## API Reference

Uses the [Spot.io REST API](https://docs.spot.io/api/) at `https://api.spotinst.io`.
