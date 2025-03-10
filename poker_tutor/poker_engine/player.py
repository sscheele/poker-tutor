from dataclasses import dataclass, field
from typing import List, Optional
from .card import Card

@dataclass
class Player:
	name: str
	stack: int
	position: int
	player_type: str = "human"  # "human" or "bot"
	hole_cards: List[Card] = field(default_factory=list)
	bet_amount: int = 0
	is_active: bool = True
	is_all_in: bool = False
	hand_description: Optional[str] = None  # Add hand description field
	
	def reset_hand(self) -> None:
		"""Reset player state for a new hand."""
		self.hole_cards = []
		self.bet_amount = 0
		self.is_active = True
		self.is_all_in = False
		self.hand_description = None  # Reset hand description
	
	def add_hole_card(self, card: Card) -> None:
		"""Add a hole card to the player's hand."""
		if len(self.hole_cards) >= 2:
			raise ValueError("Player already has two hole cards")
		self.hole_cards.append(card)
	
	def place_bet(self, amount: int) -> int:
		"""Place a bet and return the amount bet."""
		if amount > self.stack:
			amount = self.stack
		self.stack -= amount
		self.bet_amount += amount
		return amount
	
	def fold(self) -> None:
		"""Fold the current hand."""
		self.is_active = False