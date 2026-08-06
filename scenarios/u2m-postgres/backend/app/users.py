from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import User
from .schemas import UserSync


def upsert_user(session: Session, profile: UserSync) -> User:
    statement = insert(User).values(
        external_user_id=profile.external_user_id,
        email=profile.email,
        username=profile.username,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[User.external_user_id],
        set_={
            "email": statement.excluded.email,
            "username": statement.excluded.username,
            "updated_at": statement.excluded.updated_at,
            "last_login_at": statement.excluded.last_login_at,
        },
    ).returning(User)
    try:
        user = session.execute(statement).scalar_one()
        session.commit()
        return user
    except Exception:
        session.rollback()
        raise
