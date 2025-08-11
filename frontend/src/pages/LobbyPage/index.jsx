import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../services/api';
import styles from './style.module.css';
import { useAuth } from '../../context/AuthContext';

const LobbyPage = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { currentUser, logout } = useAuth();

  const handleFindGame = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await apiClient.post('/games/find-or-create');
      navigate(`/waiting/${response.data.id}`);
    } catch (err) {
      console.error("Failed to find or create a game:", err);
      setError(err.response?.data?.detail || 'Could not connect to a game. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.lobbyContainer}>
      <div className={styles.header}>
        <h1>Game Lobby - Welcome, {currentUser?.username}!</h1>
        <button onClick={logout} className={styles.logoutButton}>Logout</button>
      </div>

      <div className={styles.matchmakingBox}>
        <h2>Ready to Play?</h2>
        <p>Click the button below to find a game. We'll connect you to an available room or create a new one for you.</p>
        <button 
          onClick={handleFindGame} 
          className={styles.findButton}
          disabled={isLoading}
        >
          {isLoading ? 'Searching...' : 'Find Game'}
        </button>
        {error && <p className={styles.error}>{error}</p>}
      </div>
    </div>
  );
};

export default LobbyPage;
