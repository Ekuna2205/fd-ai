import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import RoleName
from app.models.user import RevokedToken, Role, User

ROLE_DESCRIPTIONS = {
    RoleName.ADMINISTRATOR: "Full access, including user and role management.",
    RoleName.RESEARCHER: "Manages datasets, models and evaluations.",
    RoleName.OPERATOR: "Runs verifications and reviews results.",
    RoleName.VIEWER: "Read-only access to dashboards and results.",
}


def get_or_create_role(db: Session, name: RoleName) -> Role:
    role = db.scalar(select(Role).where(Role.name == name.value))
    if role is None:
        role = Role(name=name.value, description=ROLE_DESCRIPTIONS[name])
        db.add(role)
        db.flush()
    return role


def seed_roles(db: Session) -> None:
    for name in RoleName:
        get_or_create_role(db, name)
    db.commit()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def count_users(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def list_users(db: Session, limit: int, offset: int) -> tuple[list[User], int]:
    items = db.scalars(select(User).order_by(User.created_at, User.email).limit(limit).offset(offset)).all()
    return list(items), count_users(db)


def is_token_revoked(db: Session, jti: str) -> bool:
    return db.get(RevokedToken, jti) is not None
