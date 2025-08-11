// src/components/GameTable/index.jsx
import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../../services/api';
import Player from '../Player';
import HandComponent from '../Hand';
import CardComponent from '../Card';
import styles from './style.module.css';
import { useAuth } from '../../context/AuthContext';

const parseCard = (cardStr) => ({
    id: cardStr,
    rank: cardStr.slice(0, -1),
    suit: cardStr.slice(-1),
    isSelected: false,
});

const GameTable = () => {
    const { gameId } = useParams();
    const { currentUser, socket, connectSocket } = useAuth();
    
    const [players, setPlayers] = useState([]);
    const [myHand, setMyHand] = useState([]);
    const [trick, setTrick] = useState([]);
    const [gamePhase, setGamePhase] = useState("connecting");
    const [isMyTurn, setIsMyTurn] = useState(false);
    const [prompt, setPrompt] = useState({ visible: true, message: "Connecting..." });
    const [leadSuit, setLeadSuit] = useState(null);
    const [heartsBroken, setHeartsBroken] = useState(false);
    const [roundNumber, setRoundNumber] = useState(0);

    const myUserId = currentUser?.id;
    const mySeatIndex = useRef(null);
    const navigate = useNavigate();

    useEffect(() => {
        connectSocket(gameId);
        
        const handleMessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.state) {
                const {
                    hands, phase, turn_user_id, current_trick, lead_suit,
                    hearts_broken, round_number, players: serverPlayers,
                } = msg.state;

                if (serverPlayers) {
                     const sortedPlayers = serverPlayers.sort((a, b) => a.seat_number - b.seat_number);
                     const myIdx = sortedPlayers.findIndex(p => p.user.id === myUserId);
                     mySeatIndex.current = myIdx;
                     const rotated = [...sortedPlayers.slice(myIdx), ...sortedPlayers.slice(0, myIdx)];
                     setPlayers(rotated);
                }

                if (hands && hands[myUserId]) {
                    setMyHand(hands[String(myUserId)].map(parseCard));
                }
                if (phase) setGamePhase(phase);
                if (turn_user_id) setIsMyTurn(turn_user_id === myUserId);
                if (current_trick) setTrick(current_trick);
                if (lead_suit) setLeadSuit(lead_suit);
                if (typeof hearts_broken === 'boolean') setHeartsBroken(hearts_broken);
                if (round_number) setRoundNumber(round_number);
            }

            switch (msg.event) {
                case "start_passing":
                    setGamePhase("passing");
                    setMyHand(msg.state.hands[String(myUserId)].map(parseCard));
                    setPrompt({ visible: true, message: `Select three cards to pass to the player on your ${msg.direction}.` });
                    break;
                
                case "cards_passed_update":
                    setMyHand(msg.state.hands[String(myUserId)].map(parseCard));
                    setGamePhase("playing");
                    setPrompt({ visible: true, message: "Cards have been passed! The new hand begins." });
                    setTimeout(() => setPrompt({ visible: false, message: "" }), 2500);
                    break;

                case "your_turn":
                    if (msg.user_id === myUserId) {
                        setIsMyTurn(true);
                        setPrompt({ visible: true, message: "It's your turn!" });
                    } else {
                        setIsMyTurn(false);
                        const activePlayer = players.find(p => p.user.id === msg.user_id);
                        if (activePlayer) {
                           setPrompt({ visible: true, message: `Waiting for ${activePlayer.user.username} to play...` });
                        }
                    }
                    break;
                
                case "card_played":
                    setTrick(msg.current_trick);
                    if (msg.player_id === myUserId) {
                        setMyHand(hand => hand.filter(c => c.id !== msg.card));
                    }
                    setIsMyTurn(false);
                    if (prompt.message === "It's your turn!") {
                        setPrompt({ visible: false, message: "" });
                    }
                    break;

                case "trick_end":
                    setPrompt({ visible: true, message: `${msg.winner_username} won this trick.` });
                    setTimeout(() => {
                        setTrick([]);
                        setPrompt({ visible: false, message: "" });
                    }, 2500);
                    break;

                case "error":
                    setPrompt({ visible: true, message: `Error: ${msg.message}` });
                    setTimeout(() => setPrompt({ visible: false, message: "" }), 3000);
                    break;
            }
        };
        
        if (socket.current) {
            socket.current.addEventListener('message', handleMessage);
        }

        return () => {
            if (socket.current) {
                socket.current.removeEventListener('message', handleMessage);
            }
        };
    }, [gameId, myUserId, socket, connectSocket, navigate, players, prompt.message]);

     useEffect(() => {
        const fetchGameData = async () => {
            try {
                const res = await apiClient.get(`/games/${gameId}`);
                const sortedPlayers = res.data.players.sort((a, b) => a.seat_number - b.seat_number);
                const myIdx = sortedPlayers.findIndex(p => p.user.id === myUserId);
                if(myIdx === -1) return;
                
                mySeatIndex.current = myIdx;
                const rotated = [...sortedPlayers.slice(myIdx), ...sortedPlayers.slice(0, myIdx)];
                setPlayers(rotated);

                if (socket.current && socket.current.readyState === WebSocket.OPEN) {
                   socket.current.send(JSON.stringify({ event: 'request_initial_state' }));
                } else {
                   setTimeout(() => {
                     if(socket.current) socket.current.send(JSON.stringify({ event: 'request_initial_state' }));
                   }, 1000);
                }

                setPrompt({visible: false, message: ""});
            } catch (e) {
                console.error("Failed to fetch game data", e);
                setPrompt({visible: true, message: "Game not found."});
            }
        };
        if(myUserId) fetchGameData();
    }, [gameId, myUserId, socket]);

    const handleCardClick = (clickedCard) => {
        if (gamePhase === 'passing') {
            const currentSelection = myHand.filter(c => c.isSelected);
            setMyHand(myHand.map(c => {
                if (c.id === clickedCard.id) {
                    return { ...c, isSelected: !c.isSelected };
                }
                if (!c.isSelected && currentSelection.length >= 3 && !clickedCard.isSelected) {
                    return c;
                }
                return c;
            }));
        } else if (gamePhase === 'playing' && isMyTurn) {
            const isFirstTrick = myHand.length === 13;
            
            if (isFirstTrick && !leadSuit && clickedCard.id !== '2♣') {
                setPrompt({ visible: true, message: "You must lead with the 2 of Clubs." });
                return;
            }

            if (leadSuit && myHand.some(c => c.suit === leadSuit) && clickedCard.suit !== leadSuit) {
                setPrompt({ visible: true, message: `You must follow suit: ${leadSuit}.` });
                return;
            }

            if (!leadSuit && clickedCard.suit === '♥' && !heartsBroken) {
                 setPrompt({ visible: true, message: "Hearts have not been broken yet." });
                 return;
            }

            if (isFirstTrick && leadSuit && (clickedCard.suit === '♥' || clickedCard.id === 'Q♠')) {
                if (myHand.some(c => c.suit === leadSuit && c.suit !== '♥' && c.id !== 'Q♠')) {
                     setPrompt({ visible: true, message: "You cannot play point cards on the first trick." });
                     return;
                }
            }

            socket.current.send(JSON.stringify({ event: 'play_card', card: clickedCard.id }));
            setIsMyTurn(false);
            setPrompt({ visible: false, message: "" });
        }
    };

    const handlePassCards = () => {
        const selectedCards = myHand.filter(card => card.isSelected);
        if (selectedCards.length !== 3) {
            setPrompt({ visible: true, message: "You must select exactly 3 cards." });
            return;
        }
        socket.current.send(JSON.stringify({
            event: 'pass_cards',
            cards: selectedCards.map(c => c.id)
        }));
        setPrompt({ visible: true, message: "Waiting for other players..." });
    };
    
    const playersPositions = ['bottom', 'left', 'top', 'right'];
    
    const opponentHand = (count) => Array(count).fill({ isFaceDown: true });

    if (players.length === 0) {
        return <div className={styles.gameTable}><div className={styles.prompt}>{prompt.message}</div></div>;
    }

    return (
        <div className={styles.gameTable}>
            <div className={styles.centerArea}>
                {prompt.visible && <div className={styles.prompt}>{prompt.message}</div>}
                {gamePhase === 'passing' && (
                    <button className={styles.passButton} onClick={handlePassCards} disabled={myHand.filter(c => c.isSelected).length !== 3}>
                        Pass 3 Cards
                    </button>
                )}
                <div className={styles.trickArea}>
                    {trick.map((played, index) => {
                        const player = players.find(p => p.user.id === played.player_id);
                        const playerIndex = players.indexOf(player);
                        return (
                            <div key={index} className={`${styles.playedCard} ${styles[`pos${playerIndex}`]}`}>
                               <CardComponent rank={played.card.slice(0, -1)} suit={played.card.slice(-1)} />
                            </div>
                        )
                    })}
                </div>
            </div>

            {players.map((player, index) => (
                <div key={player.user.id}>
                    <Player player={player} position={playersPositions[index]} />
                    <HandComponent 
                        cards={index === 0 ? myHand : opponentHand(player.card_count || 13)} 
                        position={playersPositions[index]} 
                        isMyHand={index === 0} 
                        onCardClick={handleCardClick}
                    />
                </div>
            ))}
        </div>
    );
};

export default GameTable;
