from sqlalchemy import (Column, Integer, String, ForeignKey, DateTime,
                        Enum as SQLEnum, UniqueConstraint)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from .database import Base

class GameStatus(str, enum.Enum):
    waiting = "waiting"
    in_progress = "in_progress"
    finished = "finished"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    games_played = relationship("GamePlayer", back_populates="user")
    won_games = relationship("Game", back_populates="winner")

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(SQLEnum(GameStatus), default=GameStatus.waiting, nullable=False)
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    winner = relationship("User", back_populates="won_games")
    players = relationship("GamePlayer", back_populates="game")
    rounds = relationship("Round", back_populates="game")

class GamePlayer(Base):
    __tablename__ = "game_players"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_score = Column(Integer, default=0, nullable=False)
    seat_number = Column(Integer, nullable=False)

    user = relationship("User", back_populates="games_played")
    game = relationship("Game", back_populates="players")

    __table_args__ = (
        UniqueConstraint('game_id', 'user_id', name='_game_user_uc'),
        UniqueConstraint('game_id', 'seat_number', name='_game_seat_uc'),
    )

class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    round_number = Column(Integer, nullable=False)

    game = relationship("Game", back_populates="rounds")
    scores = relationship("RoundScore", back_populates="round")

class RoundScore(Base):
    __tablename__ = "round_scores"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, nullable=False)

    round = relationship("Round", back_populates="scores")
    user = relationship("User")