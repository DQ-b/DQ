# -*- coding: utf-8 -*-
"""
sectoolkit 自带的**故意留洞**本地练习靶场。

⚠️ 仅供本机练习：进程只监听 127.0.0.1，绝不要绑到 0.0.0.0 或公网。
它内置了几类常见、可被 sectoolkit 探测到的弱点征兆，用于安全地演示工具效果：

* ``/item?id=...``   —— 反射 id（XSS 征兆）；id 含单引号时抛出 SQL 报错（SQLi 征兆）
* ``/search?q=...``  —— 反射 q（XSS 征兆）
* ``POST /login``    —— 表单 ``pass`` 含引号时抛 SQL 报错（演示原始请求 fuzz）
* 存在的路径         —— /admin /login /api /robots.txt /.env /config（演示目录探测）
* 未知路径           —— 稳定的“软 404”页（让目录探测能正确建立基线）

运行： ``python sectoolkit/examples/vulnerable_app.py [--port 8799]``
"""

from __future__ import annotations

import argparse
import http.server
import urllib.parse

EXISTING_PATHS = {
    "/admin": (200, "<html><h1>Admin Console</h1><form>...</form></html>"),
    "/login": (200, "<html><h1>Login</h1><form method=post action=/login></form></html>"),
    "/api": (200, '{"name":"demo-api","version":"1.0","endpoints":["/api/users"]}'),
    "/robots.txt": (200, "User-agent: *\nDisallow: /admin\nDisallow: /config"),
    "/.env": (200, "DB_PASSWORD=demo-not-a-real-secret\nAPI_KEY=demo1234567890"),
    "/config": (200, "<html><pre>debug=true; db=demo</pre></html>"),
}

SOFT_404 = "<html><body><h2>404 Not Found</h2><p>page padding padding padding</p></body></html>"
SQL_ERROR = "<html><body>You have an error in your SQL syntax near ''</body></html>"


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "DemoVulnApp/1.0"

    def log_message(self, *args):  # 静默
        pass

    def _send(self, status: int, body: str, ctype: str = "text/html") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def do_GET(self) -> None:
        parts = urllib.parse.urlsplit(self.path)
        path, query = parts.path, dict(urllib.parse.parse_qsl(parts.query))

        if path == "/":
            self._send(200, "<html><body><h1>Demo</h1>"
                            "<a href=/item?id=1>item</a> <a href=/search?q=x>search</a>"
                            "</body></html>")
            return

        # 反射 + SQL 报错征兆
        if path in ("/item", "/search"):
            val = query.get("id") or query.get("q") or ""
            if "'" in val or '"' in val:
                self._send(500, SQL_ERROR)
                return
            self._send(200, f"<html><body>you searched: {val}</body></html>")  # 原样反射
            return

        if path in EXISTING_PATHS:
            status, body = EXISTING_PATHS[path]
            ctype = "application/json" if path == "/api" else "text/plain" \
                if path in ("/robots.txt", "/.env") else "text/html"
            self._send(status, body, ctype)
            return

        self._send(404, SOFT_404)

    def do_POST(self) -> None:
        if urllib.parse.urlsplit(self.path).path != "/login":
            self._send(404, SOFT_404)
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8", "replace")
        form = dict(urllib.parse.parse_qsl(body))
        if "'" in form.get("pass", "") or '"' in form.get("pass", ""):
            self._send(500, SQL_ERROR)
            return
        self._send(200, f"<html>login attempt for user={form.get('user', '')}</html>")


def main() -> None:
    ap = argparse.ArgumentParser(description="sectoolkit 本地练习靶场（仅监听 127.0.0.1）")
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args()
    addr = ("127.0.0.1", args.port)  # 故意只绑本地回环
    print(f"[demo] 故意留洞靶场监听 http://127.0.0.1:{args.port} （仅本机，Ctrl-C 退出）")
    http.server.HTTPServer(addr, Handler).serve_forever()


if __name__ == "__main__":
    main()
