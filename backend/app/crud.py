from sqlalchemy.orm import Session
from . import models, schemas
from app.security import get_password_hash

# --- User Functions ---
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

# --- Game Functions ---
def get_game_by_id(db: Session, game_id: int):
    return db.query(models.Game).filter(models.Game.id == game_id).first()

def get_waiting_games(db: Session):
    return db.query(models.Game).filter(models.Game.status == 'waiting').all()

def create_game(db: Session):
    db_game = models.Game()
    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game

def add_player_to_game(db: Session, game: models.Game, user: models.User):
    # Check if player is already in the game to prevent duplicates
    existing_player = db.query(models.GamePlayer).filter(
        models.GamePlayer.game_id == game.id,
        models.GamePlayer.user_id == user.id
    ).first()
    if existing_player:
        return game

    current_seat_numbers = {player.seat_number for player in game.players}
    next_seat = 1
    while next_seat in current_seat_numbers:
        next_seat += 1

    player = models.GamePlayer(game_id=game.id, user_id=user.id, seat_number=next_seat)
    db.add(player)
    db.commit()
    db.refresh(game) # Refresh the game to load the new player relationship
    return game

def update_game_status(db: Session, game: models.Game, status: str):
    game.status = status
    db.add(game)
    db.commit()
    db.refresh(game)
    return game

def find_or_create_game(db: Session, user: models.User):
    # Find games that are waiting, have less than 4 players, and the user is not already in
    waiting_games = db.query(models.Game).filter(
        models.Game.status == 'waiting',
        ~models.Game.players.any(models.GamePlayer.user_id == user.id)
    ).all()

    eligible_games = [game for game in waiting_games if len(game.players) < 4]

    if eligible_games:
        game_to_join = eligible_games[0]
    else:
        game_to_join = create_game(db=db)
    
    return add_player_to_game(db=db, game=game_to_join, user=user)

def end_game(db: Session, game: models.Game, winner_id: int):
    game.status = 'finished'
    game.winner_id = winner_id
    db.add(game)
    db.commit()
    return game

# --- Round/Score Functions ---
def create_round(db: Session, game_id: int):
    db_round = models.Round(game_id=game_id)
    db.add(db_round)
    db.commit()
    db.refresh(db_round)
    return db_round

def create_round_score(db: Session, round_id: int, user_id: int, score: int):
    db_round_score = models.RoundScore(
        round_id=round_id,
        user_id=user_id,
        score=score
    )
    db.add(db_round_score)
    db.commit()
    return db_round_score

def update_player_total_score(db: Session, game_player: models.GamePlayer, score_change: int):
    game_player.total_score += score_change
    db.add(game_player)
    db.commit()
    db.refresh(game_player)
    return game_player
