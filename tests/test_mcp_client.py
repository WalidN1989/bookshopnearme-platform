from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bookshopnearme_mcp.api_client import BooksApiClient, _CACHE


@pytest.fixture(autouse=True)
def clear_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


@pytest.fixture
def mock_client():
    client = BooksApiClient(base_url="https://example.com/api", timeout=10)
    return client


def _mock_response(data: dict):
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def test_search_books(mock_client: BooksApiClient):
    expected = {"books": [{"id": "1", "title": "Harry Potter"}], "total": 1}
    with patch.object(mock_client._client, "get", return_value=_mock_response(expected)):
        result = mock_client.search_books(query="Harry Potter")
    assert result == expected


def test_search_books_cached(mock_client: BooksApiClient):
    expected = {"books": [], "total": 0}
    with patch.object(mock_client._client, "get", return_value=_mock_response(expected)) as mock_get:
        mock_client.search_books(query="test")
        mock_client.search_books(query="test")
    assert mock_get.call_count == 1  # second call served from cache


def test_get_book(mock_client: BooksApiClient):
    expected = {"id": "abc123", "title": "Sinhala Novel"}
    with patch.object(mock_client._client, "get", return_value=_mock_response(expected)):
        result = mock_client.get_book(book_id="abc123")
    assert result["id"] == "abc123"


def test_search_by_isbn(mock_client: BooksApiClient):
    expected = {"books": [{"isbn": "9780439023481"}], "total": 1}
    with patch.object(mock_client._client, "get", return_value=_mock_response(expected)):
        result = mock_client.search_by_isbn(isbn="9780439023481")
    assert result == expected


def test_find_books_by_author(mock_client: BooksApiClient):
    expected = {"books": [{"author": "Martin Wickramasinghe"}], "total": 1}
    with patch.object(mock_client._client, "get", return_value=_mock_response(expected)):
        result = mock_client.find_books_by_author(author="Martin Wickramasinghe")
    assert result == expected


def test_find_books_by_category(mock_client: BooksApiClient):
    expected = {"books": [], "total": 0}
    with patch.object(mock_client._client, "get", return_value=_mock_response(expected)):
        result = mock_client.find_books_by_category(category="Fiction")
    assert result == expected


def test_catalog_stats(mock_client: BooksApiClient):
    expected = {"total_books": 4231, "categories": 18}
    with patch.object(mock_client._client, "get", return_value=_mock_response(expected)):
        result = mock_client.catalog_stats()
    assert result["total_books"] == 4231


def test_http_error_propagates(mock_client: BooksApiClient):
    import httpx

    error_response = MagicMock()
    error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    with patch.object(mock_client._client, "get", return_value=error_response):
        with pytest.raises(httpx.HTTPStatusError):
            mock_client.search_books(query="anything")
