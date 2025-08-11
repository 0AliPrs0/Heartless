// src/components/Hand/index.jsx
import React from 'react';
import CardComponent from '../Card';
import styles from './style.module.css';

const Hand = ({ cards, position, isMyHand, onCardClick }) => {
  const myHandStyle = {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'flex-end',
      paddingBottom: '20px',
      gap: '-50px',
  };

  const containerStyles = isMyHand ? myHandStyle : {};
  
  return (
    <div className={`${styles.handContainer} ${styles[position]}`} style={containerStyles}>
      {cards.map((card, index) => (
        <div 
           key={card.id || index} 
           className={styles.cardWrapper}
           style={{ transform: card.isSelected ? 'translateY(-20px)' : 'translateY(0)', transition: 'transform 0.2s ease-out' }}
        >
          <CardComponent 
            rank={card.rank} 
            suit={card.suit} 
            isFaceDown={!isMyHand}
            isSelected={card.isSelected}
            onClick={() => isMyHand && onCardClick(card)}
          />
        </div>
      ))}
    </div>
  );
};

export default Hand;
