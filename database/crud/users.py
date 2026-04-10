# database/crud/users.py
from sqlalchemy.orm import Session
from database.models import User, Food

def get_or_create_user(db: Session, tg_id: int, username: str):
    user = db.query(User).filter(User.id == tg_id).first()
    if not user:
        user = User(id=tg_id, name=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def get_user_inventory(db: Session, user_id: int):
    return db.query(Food).filter(Food.user_id == user_id).all()
