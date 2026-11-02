"""A shared requests session with timeouts and automatic retry on transient errors."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        retry = Retry(
            total=2,                     # 1 try + 2 retries
            backoff_factor=0.5,          # 0.5s, 1s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        s = requests.Session()
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.headers["User-Agent"] = "NewsGenie/1.0 (student project)"
        _session = s
    return _session


class ProviderError(Exception):
    """Raised when a provider fails in a way the fallback chain should handle."""
