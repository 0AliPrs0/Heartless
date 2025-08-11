// src/components/Card/index.jsx
import React from 'react';
import styles from './style.module.css';

const suitToCharacter = {
  '♥': 'H',
  '♦': 'D',
  '♣': 'C',
  '♠': 'S',
};

const Card = ({ rank, suit, isFaceDown = false, isSelected, onClick }) => {
  const suitChar = suitToCharacter[suit] || suit;
  const cardName = `${rank}${suitChar}`;
  const imageUrl = isFaceDown ? '/cards/back-red.png' : `/cards/${cardName}.svg`;
  const readableName = `${rank} of ${suit}`;

  return (
    <div className={`${styles.card} ${isSelected ? styles.selected : ''}`} onClick={onClick}>
      <img src={imageUrl} alt={readableName} onError={(e) => { e.target.onerror = null; e.target.src='/cards/back-red.png' }} />
    </div>
  );
};

export default Card;
