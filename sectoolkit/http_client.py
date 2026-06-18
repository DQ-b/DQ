# -*- coding: utf-8 -*-
"""
一个极简的 HTTP 客户端封装。

优先使用 ``requests``（若已安装）以获得连接复用 / 代理 / 重定向控制，
否则自动回退到标准库 ``urllib``，保证零依赖也能运行。返回值统一为
:class:`HttpResponse`，便于 fuzzer 做差异比对。
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

try:  # 可选依赖
    import requests  # type: ignore

    _HAS_REQUESTS = True
except Exception:  # pragma: no cover - 取决于环境
    requests = None  # type: ignore
    _HAS_REQUESTS = False


DEFAULT_UA = "sectoolkit/0.1 (authorized-testing)"


@dataclass
class HttpResponse:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    elapsed: float
    error: str | None = None

    @property
    def length(self) -> int:
        return len(self.body)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    @property
    def line_count(self) -> int:
        return self.body.count(b"\n")


@dataclass
class HttpClient:
    timeout: float = 10.0
    headers: dict[str, str] = field(default_factory=dict)
    proxy: str | None = None
    verify: bool = True
    allow_redirects: bool = False

    def __post_init__(self) -> None:
        self.headers.setdefault("User-Agent", DEFAULT_UA)
        self._session = requests.Session() if _HAS_REQUESTS else None

    # ------------------------------------------------------------------ #
    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data=None,
        headers: dict | None = None,
    ) -> HttpResponse:
        merged = dict(self.headers)
        if headers:
            merged.update(headers)
        if _HAS_REQUESTS:
            return self._request_requests(method, url, params, data, merged)
        return self._request_urllib(method, url, params, data, merged)

    def get(self, url: str, **kw) -> HttpResponse:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> HttpResponse:
        return self.request("POST", url, **kw)

    # ----------------------------- 后端 ------------------------------ #
    def _request_requests(self, method, url, params, data, headers) -> HttpResponse:
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        t0 = time.perf_counter()
        try:
            resp = self._session.request(  # type: ignore[union-attr]
                method, url, params=params, data=data, headers=headers,
                timeout=self.timeout, proxies=proxies, verify=self.verify,
                allow_redirects=self.allow_redirects,
            )
            return HttpResponse(
                url=resp.url, status=resp.status_code,
                headers={k.lower(): v for k, v in resp.headers.items()},
                body=resp.content, elapsed=time.perf_counter() - t0,
            )
        except Exception as exc:  # noqa: BLE001
            return HttpResponse(url, 0, {}, b"", time.perf_counter() - t0, error=str(exc))

    def _request_urllib(self, method, url, params, data, headers) -> HttpResponse:
        if params:
            import urllib.parse
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        body = data.encode() if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        handlers = []
        if self.proxy:
            handlers.append(urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy}))
        if not self.allow_redirects:
            handlers.append(_NoRedirect())
        opener = urllib.request.build_opener(*handlers)
        t0 = time.perf_counter()
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                return HttpResponse(
                    url=resp.geturl(), status=resp.status,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    body=resp.read(), elapsed=time.perf_counter() - t0,
                )
        except urllib.error.HTTPError as exc:
            return HttpResponse(
                url, exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()},
                exc.read() if hasattr(exc, "read") else b"", time.perf_counter() - t0,
            )
        except Exception as exc:  # noqa: BLE001
            return HttpResponse(url, 0, {}, b"", time.perf_counter() - t0, error=str(exc))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def backend_name() -> str:
    return "requests" if _HAS_REQUESTS else "urllib"
