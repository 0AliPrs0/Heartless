from fastapi import APIRouter, status, Depends, HTTPException
from app import schemas, crud, models
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from typing import List

router = APIRouter(
    prefix="/games",
    tags=["Games"]
)

@router.post("/", response_model=schemas.Game, status_code=status.HTTP_201_CREATED)
def create_new_game(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    game = crud.create_game(db=db, user=current_user)
    return game

@router.get("/", response_model=List[schemas.Game])
def get_availabe_games(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    games = crud.get_waiting_games(db=db)
    return games

@router.post("/{game_id}/join", response_model=schemas.Game)
def join_existing_game(game_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    game = crud.get_game_by_id(db=db, game_id=game_id)
    
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
        
    if game.status != 'waiting':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Game is not waiting for players")

    if len(game.players) >= 4:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Game is already full")

    for player in game.players:
        if player.user_id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are already in this game")

    updated_game = crud.add_player_to_game(db=db, game=game, user=current_user)
    return updated_game