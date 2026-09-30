"""Security headers added to every response (FIX_PLAN F8).

No Content-Security-Policy: `/docs` loads Swagger UI from a CDN with an inline script, and a strict
CSP would break the page judges use. The headers below are safe for a JSON API and for `/docs`.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware:
    """Adds SECURITY_HEADERS to every HTTP response, unless the endpoint already set one."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._headers = [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers += [(k, v) for k, v in self._headers if k not in present]
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
