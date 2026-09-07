from fastapi import Header, HTTPException


def require_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """Temporary auth adapter.

    Production auth will bind this identity to the application's verified
    session/JWT in the authentication phase. No endpoint should accept a
    user_id from the request body for authorization decisions.
    """
    if not x_user_id or len(x_user_id) > 64:
        raise HTTPException(status_code=401, detail="authentication required")
    return x_user_id
