# bookshopnearme-mcp

MCP server for the [BookShopNearMe.lk](https://bookshopnearme.lk) book catalog.

## Installation

```bash
pip install bookshopnearme-mcp
```

## Usage

```bash
bookshopnearme-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `search_books` | Search by title, author, or keyword |
| `get_book` | Get full details by book ID |
| `search_by_isbn` | Look up by ISBN-10 or ISBN-13 |
| `find_books_by_author` | Browse by author name |
| `find_books_by_category` | Browse by category or genre |
| `catalog_stats` | Aggregate catalog statistics |

## Claude Desktop Config

```json
{
  "mcpServers": {
    "bookshopnearme": {
      "command": "bookshopnearme-mcp"
    }
  }
}
```

## API

The API is publicly accessible at:
`https://pthcjxgnaycbjrlsjhbt.supabase.co/functions/v1/public-books-api`

No authentication required. CORS is open. Responses are cached for 60 seconds.

Full API documentation: https://bookshopnearme.lk/api-docs.md
