import logging

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_session
from .schemas import UserSync, UserView
from .security import verify_internal_request
from .users import upsert_user

logger = logging.getLogger("u2m_backend")
app = FastAPI(title="Once Upon a Runtime U2M API", docs_url=None, redoc_url=None)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/internal/users/sync", response_model=UserView)
async def sync_user(
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserView:
    body = await request.body()
    request_id = verify_internal_request(request, body, settings)
    try:
        profile = UserSync.model_validate_json(body)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid profile") from error
    try:
        user = upsert_user(session, profile)
    except Exception:
        logger.exception("user_sync_failed", extra={"request_id": request_id})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Profile persistence failed") from None
    logger.info("user_sync_succeeded", extra={"request_id": request_id, "external_user_id": profile.external_user_id})
    return UserView.model_validate(user)
