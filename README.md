# fpr-censo-mcp

MCP Server for U.S. Census Bureau data, optimized for Puerto Rico.

## Setup

```bash
pip install -e .
export CENSUS_API_KEY=your_key  # free at https://api.census.gov/data/key_signup.html
```

## Run

```bash
# Local development (stdio)
python -m src.server

# Remote server (streamable HTTP)
python -m src.server --transport streamable-http --port 8001
```

## Deploy

```bash
export CENSUS_API_KEY=your_key
./deploy/deploy.sh
```
