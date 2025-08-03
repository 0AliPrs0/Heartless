from typing import List
from app.redis_client import redis_client

Suit = str
Rank = str

class Card:
    SUITS = {"Hearts": "♥", "Diamonds": "♦", "Clubs": "♣", "Spades": "♠"}
    SUIT_MAP_REV = {v: k for k, v in SUITS.items()}
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

    def to_str(self) -> str:
        return f"{self.rank}{self.SUITS[self.suit]}"

    @classmethod
    def from_str(cls, card_str: str):
        if not card_str or len(card_str) < 2:
            raise ValueError(f"Invalid card string format: {card_str}")
        suit_symbol = card_str[-1]
        rank_str = card_str[:-1]
        if suit_symbol not in cls.SUIT_MAP_REV:
            raise ValueError(f"Invalid suit symbol in string: {suit_symbol}")
        suit = cls.SUIT_MAP_REV[suit_symbol]
        return cls(suit, rank_str)

    def __repr__(self) -> str:
        return self.to_str()

    def __eq__(self, other) -> bool:
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank

    def __hash__(self):
        return hash((self.suit, self.rank))


class Deck:
    def __init__(self, game_id: int):
        self.game_id = game_id
        self.redis_key = f"deck:{self.game_id}"
        if not redis_client.exists(self.redis_key):
            self._create_deck()

    def _create_deck(self):
        all_cards = [Card(suit, rank).to_str() for suit in Card.SUITS for rank in Card.RANKS]
        redis_client.sadd(self.redis_key, *all_cards)

    def deal(self, num_players: int = 4, cards_per_player: int = 13) -> List[List[Card]]:
        total_cards_to_deal = num_players * cards_per_player
        if self.count() < total_cards_to_deal:
            raise ValueError("Not enough cards in the deck to deal.")
        
        dealt_cards_str = redis_client.spop(self.redis_key, total_cards_to_deal)
        dealt_cards = [Card.from_str(c) for c in dealt_cards_str]
        
        hands = [[] for _ in range(num_players)]
        for i, card in enumerate(dealt_cards):
            hands[i % num_players].append(card)
            
        return hands

    def count(self) -> int:
        return redis_client.scard(self.redis_key)

    def __len__(self) -> int:
        return self.count()


def get_trick_winner(played_cards: List[Card], lead_suit: Suit) -> Card:
    if not played_cards:
        raise ValueError("Cannot determine winner of an empty trick.")

    highest_card = played_cards[0]
    for card in played_cards[1:]:
        if card.suit == lead_suit and card.value > highest_card.value:
            highest_card = card
            
    return highest_card