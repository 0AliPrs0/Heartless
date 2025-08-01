import random
from typing import List

Suit = str
Rank = str

class Card:
    SUITS = {"Hearts": "♥", "Diamonds": "♦", "Clubs": "♣", "Spades": "♠"}
    RANKS = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }

    def __init__(self, suit: Suit, rank: Rank):
        if suit not in self.SUITS:
            raise ValueError(f"Invalid suit: {suit}")
        if rank not in self.RANKS:
            raise ValueError(f"Invalid rank: {rank}")
            
        self.suit = suit
        self.rank = rank
        self.value = self.RANKS[rank]
        
        if self.suit == 'Hearts':
            self.points = 1
        elif self.suit == 'Spades' and self.rank == 'Q':
            self.points = 13
        else:
            self.points = 0

    def __repr__(self) -> str:
        return f"{self.rank}{self.SUITS[self.suit]}"

    def __eq__(self, other) -> bool:
        return self.suit == other.suit and self.rank == other.rank


class Deck:
    def __init__(self):
        self.cards: List[Card] = self._create_deck()

    def _create_deck(self) -> List[Card]:
        return [Card(suit, rank) for suit in Card.SUITS for rank in Card.RANKS]

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def deal(self, num_players: int = 4, cards_per_player: int = 13) -> List[List[Card]]:
        if num_players * cards_per_player > len(self.cards):
            raise ValueError("Not enough cards in the deck to deal.")
            
        hands = [[] for _ in range(num_players)]
        for i in range(cards_per_player):
            for j in range(num_players):
                hands[j].append(self.cards.pop())
        return hands

    def __len__(self) -> int:
        return len(self.cards)


def get_trick_winner(played_cards: List[Card], lead_suit: Suit) -> Card:
    if not played_cards:
        raise ValueError("Cannot determine winner of an empty trick.")

    highest_card = played_cards[0]
    for card in played_cards[1:]:
        if card.suit == lead_suit and card.value > highest_card.value:
            highest_card = card
        elif highest_card.suit != lead_suit and card.suit != lead_suit:
            continue
            
    return highest_card