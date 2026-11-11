"""Bound request bytes before FastAPI parses new user mutation JSON bodies."""
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute

MAX_MUTATION_BODY_BYTES = 2 * 1024 * 1024
_LIMITED_PATHS = ('/save', '/batch-update', '/batch-delete-by-id')


class LimitedMutationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        if not self.path.endswith(_LIMITED_PATHS):
            return handler

        async def limited(request: Request):
            chunks = []
            received = 0
            async for chunk in request.stream():
                received += len(chunk)
                if received > MAX_MUTATION_BODY_BYTES:
                    raise HTTPException(413, detail={
                        'code': 'request_too_large', 'message': '单次保存请求最多 2 MiB',
                    })
                chunks.append(chunk)
            request._body = b''.join(chunks)
            try:
                return await handler(request)
            except RequestValidationError as exc:
                errors = []
                for error in exc.errors():
                    location = error.get('loc', ())
                    errors.append({
                        'row_index': next((part for part in location if isinstance(part, int)), None),
                        'field': str(location[-1]) if location else '',
                        'message': error['msg'],
                    })
                raise HTTPException(422, detail={
                    'code': 'validation_error', 'message': '请检查填写内容', 'errors': errors,
                }) from exc

        return limited
