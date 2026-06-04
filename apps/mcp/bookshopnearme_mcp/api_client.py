from __future__ import annotations

import time
from typing import Any

import httpx

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 60  # seconds


def _cache_key(*parts: Any) -> str:
    return "|".join(str(p) for p in parts)


def _from_cache(key: str) -> Any | None:
    if key in _CACHE:
        ts, value = _CACHE[key]
        if time.monotonic() - ts < _CACHE_TTL:
            return value
        del _CACHE[key]
    return None


def _to_cache(key: str, value: Any) -> None:
    _CACHE[key] = (time.monotonic(), value)


class BooksApiClient:
    def __init__(self, base_url: str, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def _get(self, path: str, params: dict | None = None) -> Any:
        key = _cache_key(path, sorted((params or {}).items()))
        cached = _from_cache(key)
        if cached is not None:
            return cached

        url = f"{self.base_url}{path}"
        response = self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        _to_cache(key, data)
        return data

    def search_books(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        return self._get("/", params={"search": query, "page": page, "limit": limit})

    def get_book(self, book_id: str) -> dict:
        return self._get(f"/{book_id}")

    def search_by_isbn(self, isbn: str) -> dict:
        return self._get("/", params={"isbn": isbn})

    def find_books_by_author(self, author: str, page: int = 1, limit: int = 20) -> dict:
        return self._get("/", params={"author": author, "page": page, "limit": limit})

    def find_books_by_category(self, category: str, page: int = 1, limit: int = 20) -> dict:
        return self._get("/", params={"category": category, "page": page, "limit": limit})

    def catalog_stats(self) -> dict:
        return self._get("/stats")

    def close(self) -> None:
        self._client.close()
