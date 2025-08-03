from fastapi import APIRouter, status, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
import json

from app import schemas, crud, models
from app.database import get_db
from app.redis_client import redis_client
from app.routers.auth import get_current_user
from app.websocket_manager import ConnectionManager
from app.game_logic.cards import Deck, Card, get_trick_winner

router = APIRouter(
    prefix="/games",
    tags=["Games"]
)

manager = ConnectionManager()

@router.post("/", response_model=schemas.Game, status_code=status.HTTP_201_CREATED)
def create_new_game(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    game = crud.create_game(db=db, user=current_user)
    return game

@router.get("/", response_model=List[schemas.Game])
def get_available_games(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
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
    if any(p.user_id == current_user.id for p in game.players):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are already in this game")
    updated_game = crud.add_player_to_game(db=db, game=game, user=current_user)
    return updated_game

@router.websocket("/{game_id}/ws")
async def websocket_endpoint(websocket: WebSocket, game_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    game = crud.get_game_by_id(db, game_id)
    if not game or not any(p.user_id == current_user.id for p in game.players):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, game_id, current_user.id)
    state_key = f"game:{game_id}:state"
    
    num_connected = len(manager.active_connections.get(game_id, []))
    if len(game.players) == 4 and num_connected == 4 and game.status == 'in_progress' and not redis_client.exists(state_key):
        await manager.broadcast(json.dumps({"event": "game_starting"}), game_id)
        
        sockets_info = manager.active_connections[game_id]
        player_user_ids = [p.user_id for p in sorted(game.players, key=lambda p: p.seat_number)]
        
        deck = Deck(game_id=game_id)
        player_hands_obj = deck.deal()
        
        initial_state = {
            "player_map": json.dumps({info["user_id"]: info["ws"].client.host for info in sockets_info}),
            "turn_user_id": player_user_ids[0],
            "current_trick": json.dumps([]),
            "lead_suit": "",
            "passed_cards": json.dumps({}),
            "phase": "passing",
            "round_scores": json.dumps({uid: 0 for uid in player_user_ids}),
            "hands": json.dumps({player_user_ids[i]: [c.to_str() for c in player_hands_obj[i]] for i in range(4)})
        }
        redis_client.hset(state_key, mapping=initial_state)

        for i, user_id in enumerate(player_user_ids):
            ws = manager.get_websocket(game_id, user_id)
            if ws:
                payload = {"event": "deal_cards", "hand": initial_state["hands"][i]}
                await manager.send_personal_message(json.dumps(payload), ws)
        
        await manager.broadcast(json.dumps({"event": "start_passing"}), game_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")
            
            raw_state = redis_client.hgetall(state_key)
            if not raw_state: continue

            if event == "play_card" and raw_state.get("phase") == "playing":
                if current_user.id != int(raw_state["turn_user_id"]): continue

                card_str = message.get("card")
                
                hands = json.loads(raw_state["hands"])
                current_trick = json.loads(raw_state["current_trick"])
                
                hands[str(current_user.id)].remove(card_str)
                current_trick.append({"user_id": current_user.id, "card": card_str})
                
                update_payload = {"hands": json.dumps(hands), "current_trick": json.dumps(current_trick)}
                if not raw_state.get("lead_suit"):
                    update_payload["lead_suit"] = Card.from_str(card_str).suit

                redis_client.hset(state_key, mapping=update_payload)
                
                player_index = next(i for i, p in enumerate(sorted(game.players, key=lambda p: p.seat_number)) if p.user_id == current_user.id)
                await manager.broadcast(json.dumps({"event": "card_played", "player_index": player_index, "card": card_str}), game_id)
                
                if len(current_trick) < 4:
                    next_player_index = (player_index + 1) % 4
                    next_user_id = sorted(game.players, key=lambda p: p.seat_number)[next_player_index].user_id
                    redis_client.hset(state_key, "turn_user_id", next_user_id)
                    
                    next_ws = manager.get_websocket(game_id, next_user_id)
                    if next_ws:
                        await manager.send_personal_message(json.dumps({"event": "your_turn"}), next_ws)
                else:
                    trick_cards_obj = [Card.from_str(item["card"]) for item in current_trick]
                    lead_suit = raw_state.get("lead_suit") or trick_cards_obj[0].suit
                    winner_card = get_trick_winner(trick_cards_obj, lead_suit)
                    winner_user_id = next(item["user_id"] for item in current_trick if item["card"] == winner_card.to_str())
                    
                    round_scores = json.loads(raw_state["round_scores"])
                    round_scores[str(winner_user_id)] += sum(c.points for c in trick_cards_obj)
                    
                    redis_client.hset(state_key, mapping={
                        "turn_user_id": winner_user_id,
                        "current_trick": json.dumps([]),
                        "lead_suit": "",
                        "round_scores": json.dumps(round_scores)
                    })
                    
                    winner_player_index = next(i for i, p in enumerate(sorted(game.players, key=lambda p: p.seat_number)) if p.user_id == winner_user_id)
                    await manager.broadcast(json.dumps({"event": "trick_end", "winner_index": winner_player_index}), game_id)

                    if not json.loads(redis_client.hget(state_key, "hands"))[str(current_user.id)]:
                        # End of round logic from previous steps
                        pass 

                    else:
                        winner_ws = manager.get_websocket(game_id, winner_user_id)
                        if winner_ws:
                            await manager.send_personal_message(json.dumps({"event": "your_turn"}), winner_ws)

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id, current_user.id)
        if not manager.active_connections.get(game_id):
            redis_client.delete(state_key)
            redis_client.delete(f"deck:{game_id}")
        await manager.broadcast(json.dumps({"event": "player_left", "user_id": current_user.id}), game_id)