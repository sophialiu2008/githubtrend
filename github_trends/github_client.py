from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, cache_dir: Path, cache_ttl_hours: int = 12, timeout: int = 30) -> None:
        self.token = token
        self.cache_dir = cache_dir
        self.cache_ttl_seconds = cache_ttl_hours * 3600
        self.timeout = timeout
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search_repositories(
        self,
        query: str,
        *,
        sort: str = "stars",
        order: str = "desc",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while len(items) < limit:
            per_page = min(100, limit - len(items))
            payload, _ = self._request_json(
                f"{self.BASE_URL}/search/repositories",
                params={
                    "q": query,
                    "sort": sort,
                    "order": order,
                    "per_page": per_page,
                    "page": page,
                },
                cache_namespace="search",
            )
            page_items = payload.get("items", [])
            if not page_items:
                break
            items.extend(page_items)
            if len(page_items) < per_page:
                break
            page += 1
        return items[:limit]

    def get_repository(self, full_name: str) -> dict[str, Any]:
        payload, _ = self._request_json(
            f"{self.BASE_URL}/repos/{quote(full_name)}",
            params=None,
            cache_namespace="repo",
        )
        return payload

    def get_readme_excerpt(self, full_name: str, max_chars: int = 420) -> str:
        try:
            payload, _ = self._request_json(
                f"{self.BASE_URL}/repos/{quote(full_name)}/readme",
                params=None,
                cache_namespace="readme",
            )
        except RuntimeError:
            return ""

        content = payload.get("content")
        if not content:
            return ""
        decoded = base64.b64decode(content).decode("utf-8", errors="replace")
        lines = [line.strip() for line in decoded.splitlines() if line.strip()]
        excerpt = " ".join(line for line in lines if not line.startswith("#"))
        excerpt = excerpt[:max_chars].strip()
        return excerpt

    def _request_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None,
        cache_namespace: str,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        query_url = url if not params else f"{url}?{urlencode(params)}"
        cache_file = self._cache_file(cache_namespace, query_url)

        cached = self._read_cache(cache_file)
        if cached is not None:
            return cached["payload"], cached.get("headers", {})

        request = Request(
            query_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "github-industry-trends-dashboard",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        for attempt in range(4):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    headers = {key: value for key, value in response.headers.items()}
                    self._write_cache(cache_file, payload, headers)
                    return payload, headers
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                headers = {key: value for key, value in exc.headers.items()}
                if exc.code in (403, 429) and self._is_rate_limited(headers, body):
                    self._wait_for_rate_limit(headers)
                    continue
                if 500 <= exc.code < 600 and attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(
                    f"GitHub API request failed with HTTP {exc.code}: {body}"
                ) from exc
            except URLError as exc:
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"GitHub API request failed: {exc}") from exc

        raise RuntimeError("GitHub API request failed after retries.")

    def _cache_file(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.cache_dir / namespace / f"{digest}.json"

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if time.time() - payload.get("cached_at", 0) > self.cache_ttl_seconds:
            return None
        return payload

    def _write_cache(self, path: Path, payload: dict[str, Any], headers: dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "cached_at": time.time(),
                    "payload": payload,
                    "headers": headers,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _is_rate_limited(headers: dict[str, str], body: str) -> bool:
        return headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in body.lower()

    @staticmethod
    def _wait_for_rate_limit(headers: dict[str, str]) -> None:
        reset_at = int(headers.get("X-RateLimit-Reset", "0") or "0")
        wait_seconds = max(int(reset_at - time.time()) + 2, 5)
        time.sleep(wait_seconds)

