from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from target_api.server.app.endpoints import router

app = FastAPI(
    title="ReMorph Financial API", 
    version="1.0.0",
    description="Complex production API serving as a proxy target for the Universal Fuzzer"
)

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 405:
        detail = f"The [{request.method}] method is not allowed on [{request.url.path}]. Please verify the HTTP verb specified in the API contract."
    elif exc.status_code == 404:
        detail = f"The route [{request.url.path}] could not be found. Please verify the endpoint version and path spelling."
    else:
        detail = exc.detail

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "rejection_reason": "Global Boundary Trap", "path": request.url.path}
    )

app.include_router(router, prefix="/api/v1")
