import random
from .card import Card, Rank, Suit

class Deck:
	def __init__(self):
		self.cards = [
			Card(rank, suit)
			for rank in Rank
			for suit in Suit
		]
		self.shuffle()

	def shuffle(self) -> None:
		"""Shuffle the deck of cards."""
		random.shuffle(self.cards)

	def draw(self) -> Card:
		"""Draw a card from the top of the deck."""
		if not self.cards:
			raise ValueError("No cards left in deck")
		return self.cards.pop()

	def reset(self) -> None:
		"""Reset the deck to its initial state and shuffle."""
		self.__init__()