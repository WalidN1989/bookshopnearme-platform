from __future__ import annotations

import os
import sys

# Allow running from the apps/mcp directory without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from mcp.server.fastmcp import FastMCP

from bookshopnearme_mcp.api_client import BooksApiClient

_BASE_URL = os.getenv(
    "BOOKS_API_BASE_URL",
    "https://pthcjxgnaycbjrlsjhbt.supabase.co/functions/v1/public-books-api",
)
_TIMEOUT = int(os.getenv("BOOKS_API_TIMEOUT", "60"))

mcp = FastMCP(
    name="bookshopnearme",
    instructions=(
        "Access the BookShopNearMe.lk catalog. "
        "Search books, retrieve details, filter by author or category, and get catalog statistics."
    ),
)

_client = BooksApiClient(base_url=_BASE_URL, timeout=_TIMEOUT)


@mcp.tool()
def search_books(query: str, page: int = 1, limit: int = 20) -> dict:
    """Search the BookShopNearMe.lk catalog by title, author, or keyword.

    Args:
        query: Search term (title, author name, keyword, etc.)
        page: Page number for pagination (default: 1)
        limit: Number of results per page (default: 20, max: 100)
    """
    return _client.search_books(query=query, page=page, limit=limit)


@mcp.tool()
def get_book(book_id: str) -> dict:
    """Retrieve full details for a specific book by its ID.

    Args:
        book_id: The unique book identifier from the catalog
    """
    return _client.get_book(book_id=book_id)


@mcp.tool()
def search_by_isbn(isbn: str) -> dict:
    """Look up a book by its ISBN-10 or ISBN-13.

    Args:
        isbn: The ISBN (with or without hyphens)
    """
    return _client.search_by_isbn(isbn=isbn)


@mcp.tool()
def find_books_by_author(author: str, page: int = 1, limit: int = 20) -> dict:
    """Find all books by a specific author.

    Args:
        author: Author name (partial match supported)
        page: Page number for pagination (default: 1)
        limit: Number of results per page (default: 20)
    """
    return _client.find_books_by_author(author=author, page=page, limit=limit)


@mcp.tool()
def find_books_by_category(category: str, page: int = 1, limit: int = 20) -> dict:
    """Browse books within a specific category or genre.

    Args:
        category: Category or genre name (e.g., "Fiction", "Self-Help", "Children")
        page: Page number for pagination (default: 1)
        limit: Number of results per page (default: 20)
    """
    return _client.find_books_by_category(category=category, page=page, limit=limit)


@mcp.tool()
def catalog_stats() -> dict:
    """Get overall statistics about the BookShopNearMe.lk catalog.

    Returns total book count, category breakdown, and other aggregate data.
    """
    return _client.catalog_stats()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
