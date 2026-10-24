from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.schemas.common import OkResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=OkResponse)
def health(db: DbSession):
    db.execute(text("SELECT 1"))
    return OkResponse()
