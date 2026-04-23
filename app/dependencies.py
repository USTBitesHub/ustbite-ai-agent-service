from fastapi import Header, Request

async def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")

async def get_user_headers(
    x_user_id: str | None = Header(None),
    x_user_email: str | None = Header(None)
) -> dict:
    return {
        "user_id": x_user_id,
        "email": x_user_email
    }
