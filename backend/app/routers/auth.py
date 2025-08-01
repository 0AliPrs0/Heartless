from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated
from jwt import decode, PyJWTError

from app import crud, schemas, models
from app.database import get_db
from app.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    create_timed_token
)
from app.core.config import settings
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception
    
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_refresh_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "refresh":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=schemas.UserBase, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_username(db, username=form_data.username)
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    return schemas.Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

@router.post("/forgot-password")
async def forgot_password(email_schema: schemas.EmailSchema, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=email_schema.email)
    if not user:
        return {"msg": "If an account with this email exists, a password reset link has been sent."}

    reset_token = create_timed_token(
        data={"sub": user.username, "purpose": "password-reset"},
        expires_in_minutes=15
    )
    reset_link = f"http://localhost:3000/reset-password?token={reset_token}"

    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[user.email],
        body=f"Please use the following link to reset your password: {reset_link}",
        subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message)
    return {"msg": "Password reset link has been sent to your email."}

@router.post("/reset-password")
async def reset_password(reset_schema: schemas.ResetPasswordSchema, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired token.",
    )
    try:
        payload = decode(reset_schema.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "password-reset":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise credentials_exception

    crud.update_user_password(db, user=user, new_password=reset_schema.new_password)
    return {"msg": "Password has been reset successfully."}

@router.post("/refresh", response_model=schemas.Token)
async def refresh_access_token(current_user: models.User = Depends(get_current_refresh_user)):
    new_access_token = create_access_token(data={"sub": current_user.username})
    new_refresh_token = create_refresh_token(data={"sub": current_user.username})
    return schemas.Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )

@router.get("/users/me", response_model=schemas.UserBase)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user