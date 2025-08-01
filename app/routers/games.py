from fastapi import APIRouter, status, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
import json

from app import schemas, crud, models
from app.database import get_db
from app.routers.auth import get_current_user
from app.websocket_manager import ConnectionManager
from app.game_logic.cards import Deck, Card, get_trick_winner

router = APIRouter(
    prefix="/games",
    tags=["Games"]
)

manager = ConnectionManager()
game_states = {}

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
    
    num_connected = len(manager.active_connections.get(game_id, []))
    if len(game.players) == 4 and num_connected == 4 and game.status == 'in_progress' and game_id not in game_states:
        await manager.broadcast(json.dumps({"event": "game_starting"}), game_id)
        
        sockets_info = manager.active_connections[game_id]
        
        game_states[game_id] = {
            "player_map": {info["user_id"]: info["ws"] for info in sockets_info},
            "turn_user_id": game.players[0].user_id,
            "current_trick": [],
            "lead_suit": None,
            "passed_cards": {},
            "phase": "passing",
            "round_scores": {info["user_id"]: 0 for info in sockets_info},
            "hands": {}
        }
        
        deck = Deck()
        deck.shuffle()
        player_hands = deck.deal()
        
        for i, player_data in enumerate(game.players):
            state = game_states[game_id]
            state["hands"][player_data.user_id] = player_hands[i]
            
            hand_as_str = [repr(card) for card in player_hands[i]]
            payload = {"event": "deal_cards", "hand": hand_as_str}
            await manager.send_personal_message(json.dumps(payload), state["player_map"][player_data.user_id])
        
        await manager.broadcast(json.dumps({"event": "start_passing"}), game_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event")
            state = game_states.get(game_id)
            if not state: continue

            if event == "play_card" and state["phase"] == "playing":
                if current_user.id != state["turn_user_id"]: continue

                card_str = message.get("card")
                suit_map = {v: k for k, v in Card.SUITS.items()}
                card_played = Card(suit_map[card_str[-1]], card_str[:-1])

                state["hands"][current_user.id] = [c for c in state["hands"][current_user.id] if c != card_played]
                state["current_trick"].append({"user_id": current_user.id, "card": card_played})
                if not state["lead_suit"]:
                    state["lead_suit"] = card_played.suit

                player_index = next(i for i, p in enumerate(game.players) if p.user_id == current_user.id)
                await manager.broadcast(json.dumps({"event": "card_played", "player_index": player_index, "card": repr(card_played)}), game_id)
                
                if len(state["current_trick"]) < 4:
                    next_player_index = (player_index + 1) % 4
                    state["turn_user_id"] = game.players[next_player_index].user_id
                    await manager.send_personal_message(json.dumps({"event": "your_turn"}), state["player_map"][state["turn_user_id"]])
                else:
                    trick_cards = [item["card"] for item in state["current_trick"]]
                    winner_card = get_trick_winner(trick_cards, state["lead_suit"])
                    winner_user_id = next(item["user_id"] for item in state["current_trick"] if item["card"] == winner_card)
                    
                    state["round_scores"][winner_user_id] += sum(c.points for c in trick_cards)
                    state["turn_user_id"] = winner_user_id
                    state["current_trick"] = []
                    state["lead_suit"] = None
                    
                    winner_player_index = next(i for i, p in enumerate(game.players) if p.user_id == winner_user_id)
                    await manager.broadcast(json.dumps({"event": "trick_end", "winner_index": winner_player_index}), game_id)

                    if not state["hands"][current_user.id]:
                        final_scores = {}
                        shoot_the_moon_user = next((uid for uid, s in state["round_scores"].items() if s == 26), None)

                        if shoot_the_moon_user:
                            for uid in state["round_scores"]:
                                final_scores[uid] = 0 if uid == shoot_the_moon_user else 26
                        else:
                            for uid, s in state["round_scores"].items():
                                final_scores[uid] = -s
                        
                        new_round = crud.create_round(db=db, game_id=game_id)
                        player_map = {p.user_id: p for p in game.players}
                        for uid, score in final_scores.items():
                            crud.create_round_score(db, round_id=new_round.id, user_id=uid, score=score)
                            crud.update_player_total_score(db, game_player=player_map[uid], score_change=score)

                        db.refresh(game)
                        
                        round_summary = {"event": "round_end_summary", "scores": final_scores, "total_scores": {p.user_id: p.total_score for p in game.players}}
                        await manager.broadcast(json.dumps(round_summary), game_id)

                        if any(p.total_score <= -100 for p in game.players):
                            winner = max(game.players, key=lambda p: p.total_score)
                            crud.end_game(db=db, game=game, winner_id=winner.user_id)
                            await manager.broadcast(json.dumps({"event": "game_over", "winner_id": winner.user_id}), game_id)
                            for ws_info in manager.active_connections[game_id]: await ws_info["ws"].close()
                            del game_states[game_id]
                            return
                        else:
                            state["phase"] = "passing"
                    else:
                        await manager.send_personal_message(json.dumps({"event": "your_turn"}), state["player_map"][state["turn_user_id"]])

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id, current_user.id)
        if game_id in game_states: del game_states[game_id]
        await manager.broadcast(json.dumps({"event": "player_left"}), game_id)