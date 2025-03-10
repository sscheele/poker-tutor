from dataclasses import dataclass
from enum import Enum, auto

class Suit(Enum):
	HEARTS = auto()
	DIAMONDS = auto()
	CLUBS = auto()
	SPADES = auto()

class Rank(Enum):
	TWO = 2
	THREE = 3
	FOUR = 4
	FIVE = 5
	SIX = 6
	SEVEN = 7
	EIGHT = 8
	NINE = 9
	TEN = 10
	JACK = 11
	QUEEN = 12
	KING = 13
	ACE = 14

@dataclass
class Card:
	rank: Rank
	suit: Suit

	def __str__(self) -> str:
		rank_symbols = {
			Rank.TWO: "2", Rank.THREE: "3", Rank.FOUR: "4",
			Rank.FIVE: "5", Rank.SIX: "6", Rank.SEVEN: "7",
			Rank.EIGHT: "8", Rank.NINE: "9", Rank.TEN: "T",
			Rank.JACK: "J", Rank.QUEEN: "Q", Rank.KING: "K",
			Rank.ACE: "A"
		}
		suit_symbols = {
			Suit.HEARTS: "♥", Suit.DIAMONDS: "♦",
			Suit.CLUBS: "♣", Suit.SPADES: "♠"
		}
		return f"{rank_symbols[self.rank]}{suit_symbols[self.suit]}"