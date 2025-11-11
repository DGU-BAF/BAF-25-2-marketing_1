from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.schemas.user_schema import UserCreate, UserLogin, UserOut
from backend.utils.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

@router.post("/signup")
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    print("🔍 받은 payload:", payload)
    print("🔍 password 타입:", type(payload.password), "값:", payload.password)
    # 아이디 중복 체크
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, "이미 존재하는 아이디입니다.")
    # 비밀번호 해시
    user = User(
        username=payload.username,
        password=hash_password(payload.password),
        height=payload.height,
        weight=payload.weight,
        gender=payload.gender,
        meals_per_day=payload.meals_per_day,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "회원가입 성공", "user": UserOut.model_validate(user, from_attributes=True)}

@router.post("/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    token = create_access_token(user.username)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/token")
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    access_token = create_access_token(user.username)
    return {"access_token": access_token, "token_type": "bearer"}

