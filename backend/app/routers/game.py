from fastapi import APIRouter, status, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json
import logging
import asyncio
import random

from app import schemas, crud, models
from app.database import get_db
from app.redis_client import redis_client
from app.routers.auth import get_current_user
from app.websocket_manager import ConnectionManager
from app.game_logic.cards import Deck, Card, get_trick_winner, Suit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["Games"])
manager = ConnectionManager()

# =================================================================================
# Helper Functions (New and Improved)
# =================================================================================

def get_game_data_as_dict(game: models.Game, state: Dict = None) -> Dict[str, Any]:
    """Creates a dictionary representation of the game, including player scores and card counts from state."""
    players_data = []
    for p in game.players:
        player_info = {
            "user": {"id": p.user.id, "username": p.user.username},
            "seat_number": p.seat_number,
            "total_score": p.total_score
        }
        if state and state.get("hands"):
            # Ensure we are accessing the hand count correctly
            player_hand = state.get("hands", {}).get(str(p.user_id), [])
            player_info["card_count"] = len(player_hand)
        players_data.append(player_info)

    return {
        "id": game.id,
        "status": game.status,
        "players": players_data,
    }

async def get_game_state(game_id: int) -> Dict[str, Any] | None:
    """Retrieves the game state from Redis."""
    state_key = f"game:{game_id}:state"
    raw_state = redis_client.hgetall(state_key)
    if not raw_state: return None
    
    # FIX: Handle strings directly, assuming decode_responses=True in Redis client.
    # No .decode() is needed.
    state = {k: json.loads(v) if isinstance(v, str) and v.startswith(('[', '{')) else v for k, v in raw_state.items()}
    
    # Ensure correct types after loading
    for key in ['round_number', 'turn_user_id', 'trick_starter_id']:
        if key in state and state[key] is not None:
            try:
                state[key] = int(state[key])
            except (ValueError, TypeError):
                logger.warning(f"Could not convert state key '{key}' with value '{state[key]}' to int for game {game_id}.")
                state[key] = None # Or handle as an error
    if 'hearts_broken' in state:
        state['hearts_broken'] = str(state['hearts_broken']) == 'True'
        
    return state

async def set_game_state(game_id: int, state: dict):
    """Saves the game state to Redis."""
    state_key = f"game:{game_id}:state"
    # Serialize complex types to JSON strings before saving
    state_to_save = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in state.items()}
    redis_client.hset(state_key, mapping=state_to_save)


def get_pass_direction(round_number: int) -> str | None:
    """Determines the card passing direction based on the round number."""
    directions = {1: "left", 2: "right", 3: "across", 4: None} # Round 4 is a "hold" round
    return directions.get((round_number - 1) % 4 + 1)

def get_pass_recipient_id(sender_id: int, direction: str, players: List[models.GamePlayer]) -> int:
    """Finds the user ID of the player to receive cards."""
    player_map = {p.user_id: p for p in players}
    sender_seat = player_map[sender_id].seat_number
    
    num_players = len(players)
    if direction == "left":
        recipient_seat = (sender_seat % num_players) + 1
    elif direction == "right":
        recipient_seat = ((sender_seat - 2 + num_players) % num_players) + 1
    elif direction == "across":
        recipient_seat = ((sender_seat + 1) % num_players) + 1
    else: # Should not happen if direction is validated
        return sender_id

    for p in players:
        if p.seat_number == recipient_seat:
            return p.user_id
    return sender_id

# =================================================================================
# Game Flow Logic
# =================================================================================

async def start_new_round(game_id: int, game: models.Game, db: Session):
    logger.info(f"[Game {game_id}] Initializing new round.")
    
    state = await get_game_state(game_id)
    round_number = state.get("round_number", 0) + 1 if state else 1

    deck = Deck(game_id=game_id)
    deck._create_deck() # Reset deck for new round
    player_hands_obj = deck.deal()
    
    players = sorted(game.players, key=lambda p: p.seat_number)
    user_ids = [p.user_id for p in players]
    hands_data = {str(uid): sorted([c.to_str() for c in hand]) for uid, hand in zip(user_ids, player_hands_obj)}
    
    starter_id = None
    for uid, hand in hands_data.items():
        if "2♣" in hand:
            starter_id = int(uid)
            break
            
    new_round_state = {
        "round_number": round_number,
        "hands": hands_data,
        "turn_user_id": starter_id,
        "trick_starter_id": starter_id,
        "phase": "passing",
        "passed_cards": {str(uid): [] for uid in user_ids},
        "current_trick": [],
        "lead_suit": None,
        "round_scores": {str(uid): 0 for uid in user_ids},
        "hearts_broken": False,
    }
    
    direction = get_pass_direction(round_number)
    if not direction:
        new_round_state["phase"] = "playing"
        await set_game_state(game_id, new_round_state)
        full_game_data = get_game_data_as_dict(game, new_round_state)
        await manager.broadcast(json.dumps({"event": "start_playing", "state": {**new_round_state, "players": full_game_data['players']}}), game_id)
        await manager.broadcast(json.dumps({"event": "your_turn", "user_id": starter_id}), game_id)
    else:
        new_round_state["pass_direction"] = direction
        await set_game_state(game_id, new_round_state)
        full_game_data = get_game_data_as_dict(game, new_round_state)
        await manager.broadcast(json.dumps({"event": "start_passing", "direction": direction, "state": {**new_round_state, "players": full_game_data['players']}}), game_id)

async def process_trick_end(game_id: int, state: dict, db: Session):
    trick = state["current_trick"]
    lead_card_str = trick[0]["card"]
    lead_suit = Card.from_str(lead_card_str).suit
    
    played_cards = [Card.from_str(p["card"]) for p in trick]
    trick_winner_card = get_trick_winner(played_cards, lead_suit)
    
    winner_id = None
    for p in trick:
        if p["card"] == trick_winner_card.to_str():
            winner_id = p["player_id"]
            break
            
    points = sum(c.points for c in played_cards)
    state["round_scores"][str(winner_id)] += points
    
    # Update state for next trick
    state["current_trick"] = []
    state["lead_suit"] = None
    state["turn_user_id"] = winner_id
    state["trick_starter_id"] = winner_id
    
    await set_game_state(game_id, state)
    
    game = crud.get_game_by_id(db, game_id)
    winner_player = next((p for p in game.players if p.user_id == winner_id), None)
    winner_username = winner_player.user.username if winner_player else "Unknown"
    full_game_data = get_game_data_as_dict(game, state)

    await manager.broadcast(json.dumps({
        "event": "trick_end", 
        "winner_id": winner_id,
        "winner_username": winner_username,
        "points": points,
        "state": {**state, "players": full_game_data['players']}
    }), game_id)
    
    await asyncio.sleep(2.5) # Pause for players to see the result
    
    # Check for round end (no cards left in anyone's hand)
    if not any(state["hands"].values()):
        await process_round_end(game_id, state, game, db)
    else:
        await manager.broadcast(json.dumps({"event": "your_turn", "user_id": winner_id}), game_id)

async def process_round_end(game_id: int, state: dict, game: models.Game, db: Session):
    # Create Round and RoundScore entries in the database
    db_round = crud.create_round(db, game_id=game_id, round_number=state["round_number"])
    
    # Check for "Shooting the Moon"
    shot_the_moon = False
    shooter_id = None
    for uid, score in state["round_scores"].items():
        if score == 26:
            shot_the_moon = True
            shooter_id = int(uid)
            break
            
    # Update total scores in the database
    for p in game.players:
        player_id = p.user_id
        score_change = 0
        if shot_the_moon:
            if player_id == shooter_id:
                score_change = 0 # Or -26 based on house rules
            else:
                score_change = 26
        else:
            score_change = state["round_scores"][str(player_id)]
        
        crud.create_round_score(db, round_id=db_round.id, user_id=player_id, score=score_change)
        # Correctly call update_player_total_score with the GamePlayer object
        crud.update_player_total_score(db, game_player=p, score_change=score_change)
    
    db.refresh(game) # Refresh to get updated total_scores
    
    # Check for game end
    if any(p.total_score >= 100 for p in game.players):
        # Find winner (lowest score)
        winner = min(game.players, key=lambda p: p.total_score)
        crud.end_game(db, game=game, winner_id=winner.user_id)
        await manager.broadcast(json.dumps({"event": "game_over", "winner": winner.user.username}), game_id)
    else:
        # Start new round after a delay
        await asyncio.sleep(5)
        await start_new_round(game_id, game, db)

# =================================================================================
# API Endpoints
# =================================================================================

@router.post("/find-or-create", response_model=schemas.Game)
async def find_or_create_game_endpoint(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    game = crud.find_or_create_game(db=db, user=current_user)
    
    db.refresh(game) # Refresh to get the latest player count
    
    if game.status == 'waiting' and len(game.players) == 4:
        logger.info(f"[Game {game.id}] Four players have joined. Triggering game start.")
        crud.update_game_status(db=db, game=game, status="in_progress")
        
        # Important: Refresh game object to get latest player list
        db.refresh(game)
        
        await start_new_round(game.id, game, db)
        
        await asyncio.sleep(0.5) 
        full_game_data = get_game_data_as_dict(game)
        await manager.broadcast(json.dumps({"event": "game_starting", "game": full_game_data}), game.id)

    return game

@router.get("/{game_id}", response_model=schemas.Game)
def get_game_details(game_id: int, db: Session = Depends(get_db)):
    game = crud.get_game_by_id(db=db, game_id=game_id)
    if not game: raise HTTPException(status_code=404, detail="Game not found")
    return game

# =================================================================================
# WebSocket Endpoint (Main Game Logic)
# =================================================================================

@router.websocket("/{game_id}/ws")
async def websocket_endpoint(websocket: WebSocket, game_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    current_user = await get_current_user(token=token, db=db)
    game = crud.get_game_by_id(db, game_id)
    if not game or not any(p.user_id == current_user.id for p in game.players):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, game_id, current_user.id)
    logger.info(f"[Game {game_id}] User {current_user.id} CONNECTED.")
    
    db.refresh(game)
    state = await get_game_state(game_id)
    full_game_data = get_game_data_as_dict(game, state)
    await manager.broadcast(json.dumps({"event": "player_update", "game": full_game_data}), game_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")
            logger.info(f"[Game {game_id}] Received event '{event}' from user {current_user.id}")

            state = await get_game_state(game_id)
            if not state and event not in ['request_initial_state']:
                logger.warning(f"[Game {game_id}] No state found for event '{event}'")
                continue

            # --- Event Handlers ---
            if event == "request_initial_state":
                if state:
                    full_game_data = get_game_data_as_dict(game, state)
                    await manager.send_personal_message(json.dumps({"event": "initial_state", "state": {**state, "players": full_game_data['players']}}), websocket)

            elif event == "pass_cards":
                if state["phase"] != "passing" or str(current_user.id) not in state["passed_cards"] or state["passed_cards"][str(current_user.id)]:
                    continue 

                cards_to_pass = message.get("cards", [])
                if len(cards_to_pass) != 3:
                    await manager.send_personal_message(json.dumps({"event": "error", "message": "You must pass exactly 3 cards."}), websocket)
                    continue
                
                state["passed_cards"][str(current_user.id)] = cards_to_pass
                state["hands"][str(current_user.id)] = [c for c in state["hands"][str(current_user.id)] if c not in cards_to_pass]
                
                if all(len(v) == 3 for v in state["passed_cards"].values()):
                    logger.info(f"[Game {game_id}] All players have passed cards. Distributing.")
                    direction = state["pass_direction"]
                    
                    for sender_id_str, cards in state["passed_cards"].items():
                        sender_id = int(sender_id_str)
                        recipient_id = get_pass_recipient_id(sender_id, direction, game.players)
                        state["hands"][str(recipient_id)].extend(cards)
                    
                    state["phase"] = "playing"
                    for uid in state["hands"]: state["hands"][uid] = sorted(state["hands"][uid])
                    await set_game_state(game_id, state)
                    
                    full_game_data = get_game_data_as_dict(game, state)
                    await manager.broadcast(json.dumps({"event": "cards_passed_update", "state": {**state, "players": full_game_data['players']}}), game_id)
                    await manager.broadcast(json.dumps({"event": "your_turn", "user_id": state["turn_user_id"]}), game_id)
                else:
                    await set_game_state(game_id, state)

            elif event == "play_card":
                card_str = message.get("card")
                player_id = current_user.id
                hand = state["hands"][str(player_id)]
                played_card = Card.from_str(card_str)
                
                # --- Server-Side Validation ---
                is_valid = True
                error_message = ""
                if state["turn_user_id"] != player_id:
                    is_valid = False; error_message = "Not your turn."
                elif card_str not in hand:
                    is_valid = False; error_message = "Card not in hand."
                else:
                    is_first_trick = len(state["hands"][str(player_id)]) == 13
                    lead_suit = state.get("lead_suit")
                    
                    # Rule: Must lead with 2 of Clubs on first trick
                    if is_first_trick and not lead_suit and card_str != '2♣' and '2♣' in hand:
                        is_valid = False; error_message = "Must lead with 2 of Clubs."
                    # Rule: Must follow suit
                    elif lead_suit and played_card.suit != lead_suit and any(Card.from_str(c).suit == lead_suit for c in hand):
                        is_valid = False; error_message = f"Must follow suit ({lead_suit})."
                    # Rule: Cannot lead with Hearts unless broken
                    elif not lead_suit and played_card.suit == 'Hearts' and not state.get('hearts_broken', False):
                        is_valid = False; error_message = "Hearts have not been broken."
                    # Rule: Cannot play points on the first trick
                    elif is_first_trick and lead_suit and played_card.points > 0:
                        if any(Card.from_str(c).points == 0 for c in hand):
                           is_valid = False; error_message = "Cannot play point cards on the first trick."

                if not is_valid:
                    await manager.send_personal_message(json.dumps({"event": "error", "message": error_message}), websocket)
                    continue

                # --- Update State ---
                state["hands"][str(player_id)].remove(card_str)
                if played_card.suit == "Hearts": state["hearts_broken"] = True
                if played_card.to_str() == "Q♠": state["hearts_broken"] = True # Q of Spades also breaks hearts
                
                if not state["current_trick"]:
                    state["lead_suit"] = played_card.suit
                
                state["current_trick"].append({"player_id": player_id, "card": card_str})
                
                # Find next player
                if len(state["current_trick"]) < 4:
                    current_seat = [p for p in game.players if p.user_id == player_id][0].seat_number
                    next_seat = (current_seat % 4) + 1
                    next_player_id = [p for p in game.players if p.seat_number == next_seat][0].user_id
                    state["turn_user_id"] = next_player_id
                else:
                    state["turn_user_id"] = None # No one's turn until trick is processed
                
                await set_game_state(game_id, state)
                full_game_data = get_game_data_as_dict(game, state)
                
                await manager.broadcast(json.dumps({
                    "event": "card_played",
                    "player_id": player_id,
                    "card": card_str,
                    "current_trick": state["current_trick"],
                    "state": {**state, "players": full_game_data['players']}
                }), game_id)

                if len(state["current_trick"]) == 4:
                    await process_trick_end(game_id, state, db)
                else:
                    await manager.broadcast(json.dumps({"event": "your_turn", "user_id": state["turn_user_id"]}), game_id)

    except WebSocketDisconnect:
        logger.warning(f"[Game {game_id}] User {current_user.id} DISCONNECTING.")
        manager.disconnect(websocket, game_id, current_user.id)
        db.refresh(game)
        state = await get_game_state(game_id)
        full_game_data = get_game_data_as_dict(game, state)
        await manager.broadcast(json.dumps({"event": "player_update", "game": full_game_data}), game_id)
