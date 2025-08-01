from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from .models import GameStatus

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserBase(BaseModel):
    id: int
    username: str
    email: EmailStr

    class Config:
        from_attributes = True

class RoundScoreBase(BaseModel):
    user_id: int
    score: int

    class Config:
        from_attributes = True

class RoundBase(BaseModel):
    id: int
    round_number: int
    scores: List[RoundScoreBase] = []

    class Config:
        from_attributes = True

class GamePlayerBase(BaseModel):
    user: UserBase
    total_score: int
    seat_number: int

    class Config:
        from_attributes = True

class Game(BaseModel):
    id: int
    status: GameStatus
    created_at: datetime
    winner: Optional[UserBase] = None
    players: List[GamePlayerBase] = []
    rounds: List[RoundBase] = []

    class Config:
        from_attributes = True

class User(UserBase):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str


class TokenData(BaseModel):
    username: str | None = None

class EmailSchema(BaseModel):
    email: EmailStr

class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str
