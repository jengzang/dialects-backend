from fastapi import Request

from app.service.logging.config.diagnostics import MAX_DIAGNOSTIC_BODY_BYTES


async def capture_request_body(request: Request) -> bytes:
    """Read request body and restore stream for downstream handlers."""
    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive
    return body


def attach_diagnostic_body_capture(request: Request):
    """
    Tee request-body chunks into a bounded buffer while downstream consumes them.

    This avoids eagerly reading the full body for every mutating API request.
    """
    original_receive = request._receive
    captured = bytearray()
    total_size = 0
    truncated = False

    async def receive():
        nonlocal total_size, truncated
        message = await original_receive()
        if message.get("type") == "http.request":
            chunk = message.get("body", b"") or b""
            if chunk:
                total_size += len(chunk)
                remaining = MAX_DIAGNOSTIC_BODY_BYTES - len(captured)
                if remaining > 0:
                    captured.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True
        return message

    request._receive = receive

    def get_state():
        return bytes(captured), truncated, total_size

    return get_state
