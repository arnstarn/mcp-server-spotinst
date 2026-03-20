# mcp-server-spotinst

MCP server for the [Spot.io (Spotinst)](https://spot.io/) API. Exposes Ocean clusters, VNGs, Elastigroups, and cost data as MCP tools.

## Tools

| Tool | Description |
|------|-------------|
| `list_clusters` | List all Ocean K8s clusters |
| `get_cluster` | Get details of a specific Ocean cluster |
| `list_vngs` | List Virtual Node Groups (launch specs) |
| `get_vng` | Get VNG details |
| `list_elastigroups` | List all Elastigroups |
| `get_elastigroup` | Get Elastigroup details |
| `get_cluster_nodes` | List nodes in an Ocean cluster |
| `get_cluster_costs` | Get cost breakdown for a date range |

## Setup

### Environment Variables

```bash
export SPOTINST_TOKEN="your-spotinst-api-token"
export SPOTINST_ACCOUNT_ID="act-xxxxxxxx"
```

### Install

```bash
pip install -e .
```

### Claude Code Config

Add to your MCP settings:

```json
{
  "mcpServers": {
    "spotinst": {
      "command": "mcp-server-spotinst",
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

## API Reference

Uses the [Spot.io REST API](https://docs.spot.io/api/) at `https://api.spotinst.io`.
