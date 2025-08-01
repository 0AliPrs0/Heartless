from sqlalchemy.orm import Session
from . import models, schemas
from app.security import get_password_hash

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_password(db: Session, user: models.User, new_password: str):
    hashed_password = get_password_hash(new_password)
    user.hashed_password = hashed_password
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_game(db:Session, user: models.User):
    db_game = models.Game()
    db.add(db_game)
    db.commit()
    db.refresh(db_game)

    player = models.GamePlayer(
        game_id=db_game.id,
        user_id=user.id,
        seat_number=1
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    return db_game

def get_waiting_games(db:Session):
    return db.query(models.Game).filter(models.Game.status == 'waiting').all()

def get_game_by_id(db:Session, game_id:int):
    return db.query(models.Game).filter(models.Game.id == game_id).first()

def add_player_to_game(db: Session, game: models.Game, user: models.User):
    current_seat_numbers = {player.seat_number for player in game.players}
    next_seat = 1
    while next_seat in current_seat_numbers:
        next_seat += 1

    player = models.GamePlayer(
        game_id=game.id,
        user_id=user.id,
        seat_number=next_seat
    )
    db.add(player)
    
    if len(game.players) + 1 == 4:
        game.status = 'in_progress'
        db.add(game)

    db.commit()
    db.refresh(game)
    return game

