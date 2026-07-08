from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, StudentParent
from ..schemas import UserRegister, UserLogin, UserOut, TokenOut
from ..security import hash_password, verify_password, create_token
from ..deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if payload.role not in ("student", "parent"):
        raise HTTPException(status_code=400, detail="角色仅支持 student / parent")
    if db.query(User).filter_by(username=payload.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    pw_hash, pw_salt = hash_password(payload.password)
    user = User(
        username=payload.username,
        password_hash=pw_hash,
        password_salt=pw_salt,
        role=payload.role,
        nickname=payload.nickname,
        grade=payload.grade if payload.role == "student" else None,
        phone=payload.phone if payload.role == "parent" else None,
        home_lat=payload.home_lat if payload.role == "student" else None,
        home_lng=payload.home_lng if payload.role == "student" else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # 生成展示绑定码（家长据此绑定孩子）
    if user.role == "student":
        user.bind_code = f"S{user.id:05d}"
        db.commit()
    token = create_token(user.id, user.role)
    return {"access_token": token, "user": UserOut.model_validate(user)}


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash, user.password_salt or ""):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user.id, user.role)
    return {"access_token": token, "user": UserOut.model_validate(user)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
