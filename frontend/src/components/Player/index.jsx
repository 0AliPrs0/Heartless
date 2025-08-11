import React from 'react';
import styles from './style.module.css';

const Player = ({ player, position }) => {
  if (!player || !player.user) {
    return <div className={`${styles.playerInfo} ${styles[position]}`}></div>;
  }

  return (
    <div className={`${styles.playerInfo} ${styles[position]}`}>
      <img src={`https://i.pravatar.cc/150?u=${player.user.username}`} alt={player.user.username} className={styles.avatar} />
      <span className={styles.name}>{player.user.username}</span>
      <span className={styles.score}>Score: {player.total_score}</span>
    </div>
  );
};

export default Player;