// src/pages/WaitingRoomPage/index.jsx
import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../../services/api';
import styles from './style.module.css';
import { useAuth } from '../../context/AuthContext';

const WaitingRoomPage = () => {
  const { gameId } = useParams();
  const navigate = useNavigate();
  const { socket, connectSocket } = useAuth();
  const [game, setGame] = useState(null);
  const [error, setError] = useState('');
  const hasNavigated = useRef(false);

  useEffect(() => {
    connectSocket(gameId);

    const fetchInitialData = async () => {
      try {
        const response = await apiClient.get(`/games/${gameId}`);
        setGame(response.data);
        if (response.data.status === 'in_progress' && !hasNavigated.current) {
          hasNavigated.current = true;
          navigate(`/game/${gameId}`);
        }
      } catch (err) {
        setError('Failed to load game data. The game may not exist.');
        console.error(err);
      }
    };
    fetchInitialData();
  }, [gameId, connectSocket, navigate]);

  useEffect(() => {
    if (!socket.current) return;

    const handleMessage = (event) => {
      const message = JSON.parse(event.data);

      const processGameUpdate = (updatedGame) => {
        if (!updatedGame) return;
        setGame(updatedGame);
        if (updatedGame.status === 'in_progress' && !hasNavigated.current) {
          hasNavigated.current = true;
          navigate(`/game/${gameId}`);
        }
      };

      if (message.event === 'player_update' || message.event === 'game_starting') {
        processGameUpdate(message.game);
      }
    };

    socket.current.addEventListener('message', handleMessage);

    return () => {
      if (socket.current) {
        socket.current.removeEventListener('message', handleMessage);
      }
    };
  }, [socket, gameId, navigate]);

  if (error) {
    return <div className={styles.container}><p className={styles.error}>{error}</p></div>;
  }

  if (!game) {
    return <div className={styles.container}><div className={styles.spinner}></div><p>Loading Game...</p></div>;
  }

  return (
    <div className={styles.container}>
      <div className={styles.waitingBox}>
        <h2>Game #{game.id}</h2>
        <p className={styles.statusText}>Waiting for players to join... ({game.players.length} / 4)</p>
        <ul className={styles.playerList}>
          {game.players.map(player => (
            <li key={player.user.id}>
              <img src={`https://i.pravatar.cc/150?u=${player.user.username}`} alt="avatar" />
              {player.user.username}
            </li>
          ))}
        </ul>
        {game.players.length < 4 && <div className={styles.spinner}></div>}
        <p className={styles.shareInfo}>Share game ID <strong>{game.id}</strong> with friends!</p>
      </div>
    </div>
  );
};

export default WaitingRoomPage;
