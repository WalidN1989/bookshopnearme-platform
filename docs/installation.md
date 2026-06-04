# Installation

## Prerequisites

- Python 3.12+
- `pip` or `uv`

## Local Development Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd bookshopnearme-platform

# 2. Create a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install all packages in editable mode
pip install -e ".[dev]"
pip install -e apps/mcp
pip install -e apps/gsc-agent

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your values

# 5. Seed the database with sample data
python scripts/seed.py

# 6. Run the tests
pytest
```

## Running the MCP Server Locally

```bash
bookshopnearme-mcp
# or
python -m bookshopnearme_mcp.server
```

## Running the GSC Agent Manually

```bash
python -m gsc_agent.agent
```
