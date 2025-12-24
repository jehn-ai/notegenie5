from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request, HTTPException
import logging

# Configure logging
logger = logging.getLogger("notegenie")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class HideServerErrorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as http_exc:
            # Pass through FastAPI HTTPExceptions (like OpenRouter 429/500)
            return Response(
                content=str(http_exc.detail),
                status_code=http_exc.status_code,
                media_type="application/json"
            )
        except Exception as e:
            # Log the actual error internally for debugging
            logger.error(f"Unhandled error: {str(e)}", exc_info=True)
            # Return generic message to client
            return Response(
                content="Internal Server Error",
                status_code=500,
                media_type="text/plain"
            )
