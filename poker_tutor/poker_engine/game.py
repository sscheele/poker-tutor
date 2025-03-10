import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum, auto
from .deck import Deck
from .player import Player
from .card import Card
from .hand_evaluator import evaluate_hand, compare_hands, HandRank

logger = logging.getLogger(__name__)

class Street(Enum):
	PREFLOP = auto()
	FLOP = auto()
	TURN = auto()
	RIVER = auto()

@dataclass
class Game:
	players: List[Player]
	deck: Deck = field(default_factory=Deck)
	community_cards: List[Card] = field(default_factory=list)
	pot: int = 0
	current_street: Street = Street.PREFLOP
	current_bet: int = 0
	hand_history: List[Dict] = field(default_factory=list)  # Track actions and cards for each street
	active_player_idx: int = 0
	dealer_pos: int = 0  # Add dealer position tracking
	small_blind: int = 50
	big_blind: int = 100
	last_aggressor: Optional[int] = None
	round_bets: Dict[int, int] = field(default_factory=dict)
	players_acted: Dict[int, bool] = field(default_factory=dict)  # Track who has acted this round
	side_pots: List[Tuple[int, List[int]]] = field(default_factory=list)  # [(amount, [eligible_player_indices])]
	game_over: bool = False
	eliminated_players: List[int] = field(default_factory=list)
	waiting_for_next_hand: bool = False  # Add waiting state field
	small_blind_pos: int = -1  # Track small blind position
	big_blind_pos: int = -1    # Track big blind position

	def start_hand(self) -> None:
		"""Start a new hand, deal cards to players."""
		self.deck.reset()
		self.community_cards = []
		self.pot = 0
		self.current_street = Street.PREFLOP
		self.current_bet = self.big_blind
		self.last_aggressor = None
		self.round_bets = {}
		self.players_acted.clear()
		self.hand_history = []  # Reset hand history for new hand
		
		# Ensure all non-eliminated players are active
		for i, player in enumerate(self.players):
			if i not in self.eliminated_players:
				player.is_active = True
				player.reset_hand()
			else:
				player.is_active = False
		
		# Calculate blind positions relative to dealer, skipping eliminated players
		self.small_blind_pos = (self.dealer_pos + 1) % len(self.players)
		while self.small_blind_pos in self.eliminated_players:
			self.small_blind_pos = (self.small_blind_pos + 1) % len(self.players)
			
		self.big_blind_pos = (self.small_blind_pos + 1) % len(self.players)
		while self.big_blind_pos in self.eliminated_players:
			self.big_blind_pos = (self.big_blind_pos + 1) % len(self.players)
		
		# Set initial active player (UTG - after BB)
		self.active_player_idx = (self.big_blind_pos + 1) % len(self.players)
		while self.active_player_idx in self.eliminated_players:
			self.active_player_idx = (self.active_player_idx + 1) % len(self.players)
		
		# Deal cards to active players
		for i, player in enumerate(self.players):
			if player.is_active:
				player.add_hole_card(self.deck.draw())
				player.add_hole_card(self.deck.draw())
		
		# Post blinds using stored positions
		self.pot += self.players[self.small_blind_pos].place_bet(self.small_blind)
		self.pot += self.players[self.big_blind_pos].place_bet(self.big_blind)
		self.round_bets[self.small_blind_pos] = self.small_blind
		self.round_bets[self.big_blind_pos] = self.big_blind

		# Record initial hand state
		self.hand_history.append({
			'street': self.current_street.name,
			'community_cards': [],
			'actions': [
				{'player': self.small_blind_pos, 'action': 'small_blind', 'amount': self.small_blind},
				{'player': self.big_blind_pos, 'action': 'big_blind', 'amount': self.big_blind}
			]
		})



	def handle_action(self, action: str, amount: Optional[int] = None) -> bool:
		"""Handle a player action (fold, call, or raise). Returns True if action was valid."""
		player = self.get_active_player()
		self.players_acted[self.active_player_idx] = True  # Mark player as having acted
		logger.debug(f"Handling action: {action} with amount {amount} for player {player.name}")
		
		# Record the action in hand history
		current_street_history = next((h for h in self.hand_history if h['street'] == self.current_street.name), None)
		if current_street_history is None:
			current_street_history = {
				'street': self.current_street.name,
				'community_cards': [str(card) for card in self.community_cards],
				'actions': []
			}
			self.hand_history.append(current_street_history)
		
		if action == "fold":
			player.is_active = False
			current_street_history['actions'].append({
				'player': self.active_player_idx,
				'action': 'fold'
			})
			logger.debug(f"Player {player.name} folded")
		elif action == "call":
			to_call = self.current_bet - (self.round_bets.get(self.active_player_idx, 0))
			if to_call == 0:
				# Explicitly record the check in round_bets to track player action
				self.round_bets[self.active_player_idx] = 0
				current_street_history['actions'].append({
					'player': self.active_player_idx,
					'action': 'check'
				})
				logger.debug(f"Player {player.name} checked")
			else:
				bet_amount = player.place_bet(to_call)
				self.pot += bet_amount
				self.round_bets[self.active_player_idx] = self.round_bets.get(self.active_player_idx, 0) + bet_amount
				current_street_history['actions'].append({
					'player': self.active_player_idx,
					'action': 'call',
					'amount': to_call
				})
				logger.debug(f"Player {player.name} called {to_call}, pot now {self.pot}")
		elif action == "raise":
			if amount is None or amount <= self.current_bet:
				logger.debug(f"Invalid raise amount: {amount}")
				return False
			to_raise = amount - (self.round_bets.get(self.active_player_idx, 0))
			if to_raise > 0:
				bet_amount = player.place_bet(to_raise)
				self.pot += bet_amount
				self.round_bets[self.active_player_idx] = self.round_bets.get(self.active_player_idx, 0) + bet_amount
				self.current_bet = amount
				self.last_aggressor = self.active_player_idx
				current_street_history['actions'].append({
					'player': self.active_player_idx,
					'action': 'raise',
					'amount': amount
				})
				logger.debug(f"Player {player.name} raised to {amount}, pot now {self.pot}")
		
		return self.advance_action()

	def advance_action(self) -> bool:
		"""Advance to the next player or street. Returns True if hand continues."""
		active_players = [p for p in self.players if p.is_active]
		logger.debug(f"Advancing action with {len(active_players)} active players")
		
		if len(active_players) == 1:
			# Single player wins uncontested
			winner_idx = next(i for i, p in enumerate(self.players) if p.is_active)
			self.players[winner_idx].stack += self.pot
			self.pot = 0
			# Start next hand after uncontested win
			self.start_next_hand()
			return False

		next_idx = (self.active_player_idx + 1) % len(self.players)
		while not self.players[next_idx].is_active:
			next_idx = (next_idx + 1) % len(self.players)

		# Check if betting round is complete
		logger.debug(f"Has acted: {[self.players_acted.get(i, False) for i, p in enumerate(self.players)]}")
		all_acted = all(self.players_acted.get(i, False) for i, p in enumerate(self.players) if p.is_active)
		logger.debug(f"All acted: {all_acted}")
		betting_complete = (next_idx == self.last_aggressor) or (self.last_aggressor is None and self.all_players_even() and all_acted)

		if betting_complete:
			logger.debug("Round of betting complete")
			if self.current_street == Street.RIVER:
				# Trigger showdown
				self.handle_showdown()
				return False
			self.deal_next_street()
			self.reset_betting_round()
			self.active_player_idx = next_idx
			logger.debug(f"Advanced to {self.current_street.name}, active player: {self.players[next_idx].name}")
		else:
			self.active_player_idx = next_idx
			logger.debug(f"Next player: {self.players[next_idx].name}")

		return True

	def all_players_even(self) -> bool:
		"""Check if all active players have bet the same amount."""
		active_bets = [self.round_bets.get(i, 0) for i, p in enumerate(self.players) if p.is_active]
		return len(set(active_bets)) <= 1

	def reset_betting_round(self) -> None:
		"""Reset betting round state."""
		self.current_bet = 0
		self.round_bets.clear()
		self.last_aggressor = None
		self.players_acted.clear()  # Reset who has acted for the new street

	def deal_next_street(self) -> None:
		"""Deal community cards for the next street."""
		if self.current_street == Street.PREFLOP:
			# Deal flop
			for _ in range(3):
				self.community_cards.append(self.deck.draw())
			self.current_street = Street.FLOP
		elif self.current_street == Street.FLOP:
			# Deal turn
			self.community_cards.append(self.deck.draw())
			self.current_street = Street.TURN
		elif self.current_street == Street.TURN:
			# Deal river
			self.community_cards.append(self.deck.draw())
			self.current_street = Street.RIVER

	def get_active_player(self) -> Player:
		"""Get the current active player."""
		return self.players[self.active_player_idx]

	def handle_showdown(self) -> List[Tuple[int, int]]:
		"""Handle showdown and return list of (player_index, amount_won) tuples."""
		logger.debug("Handling showdown")
		# Calculate side pots if needed
		self.calculate_side_pots()
		
		# Evaluate all active players' hands and set descriptions
		player_hands = []
		hand_rank_names = {
			HandRank.HIGH_CARD: "High Card",
			HandRank.PAIR: "Pair",
			HandRank.TWO_PAIR: "Two Pair",
			HandRank.THREE_OF_KIND: "Three of a Kind",
			HandRank.STRAIGHT: "Straight",
			HandRank.FLUSH: "Flush",
			HandRank.FULL_HOUSE: "Full House",
			HandRank.FOUR_OF_KIND: "Four of a Kind",
			HandRank.STRAIGHT_FLUSH: "Straight Flush"
		}
		
		for i, player in enumerate(self.players):
			if player.is_active:
				hand_rank, best_cards = evaluate_hand(player.hole_cards, self.community_cards)
				player_hands.append((i, (hand_rank, best_cards)))
				# Set hand description
				player.hand_description = hand_rank_names[hand_rank]
		
		winnings = []  # List of (player_index, amount) tuples
		
		# Handle main pot and side pots
		for pot_amount, eligible_players in self.side_pots + [(self.pot, [i for i, p in enumerate(self.players) if p.is_active])]:
			if not pot_amount:
				continue
				
			# Filter hands for eligible players
			eligible_hands = [(i, hand) for i, hand in player_hands if i in eligible_players]
			if not eligible_hands:
				continue
			
			# Find winners of this pot
			winners = self.find_pot_winners(eligible_hands)
			split_amount = pot_amount // len(winners)
			remainder = pot_amount % len(winners)
			
			# Distribute pot to winners
			for winner_idx in winners:
				amount = split_amount + (1 if remainder > 0 else 0)
				remainder -= 1
				winnings.append((winner_idx, amount))
				self.players[winner_idx].stack += amount
		
		self.pot = 0
		self.side_pots.clear()
		
		# Set waiting state instead of starting next hand immediately
		self.waiting_for_next_hand = True
		return winnings

	def find_pot_winners(self, player_hands: List[Tuple[int, Tuple[HandRank, List[Card]]]]) -> List[int]:
		"""Find the winner(s) among the given hands. Returns list of player indices."""
		if not player_hands:
			return []
			
		best_hand = player_hands[0]
		winners = [best_hand[0]]
		
		for i in range(1, len(player_hands)):
			curr_player_idx, curr_hand = player_hands[i]
			comparison = compare_hands(curr_hand, best_hand[1])
			
			if comparison > 0:
				# Current hand is better
				best_hand = (curr_player_idx, curr_hand)
				winners = [curr_player_idx]
			elif comparison == 0:
				# Tie
				winners.append(curr_player_idx)
				
		return winners

	def start_next_hand(self) -> None:
		"""Start the next hand, removing eliminated players."""
		# Reset waiting state
		self.waiting_for_next_hand = False
		
		# Remove players with no money
		for i, player in enumerate(self.players):
			if player.stack == 0 and i not in self.eliminated_players:
				self.eliminated_players.append(i)
				logger.debug(f"Player {player.name} eliminated")
		
		# Check if human player is eliminated
		human_idx = next((i for i, p in enumerate(self.players) if p.player_type == "human"), None)
		if human_idx is not None and human_idx in self.eliminated_players:
			self.game_over = True
			logger.debug("Game over - human player eliminated")
			return
		
		# Check if only one player remains
		active_players = [i for i, p in enumerate(self.players) if i not in self.eliminated_players]
		if len(active_players) <= 1:
			self.game_over = True
			logger.debug("Game over - only one player remains")
			return
		
		# Advance dealer position before starting new hand
		self.dealer_pos = (self.dealer_pos + 1) % len(self.players)
		while self.dealer_pos in self.eliminated_players:
			self.dealer_pos = (self.dealer_pos + 1) % len(self.players)
		
		# Reactivate all non-eliminated players
		for i, player in enumerate(self.players):
			if i not in self.eliminated_players:
				player.is_active = True
		
		# Start new hand
		self.start_hand()
		logger.debug(f"Started new hand with dealer at position {self.dealer_pos}")

	def calculate_side_pots(self) -> None:
		"""Calculate side pots based on all-in players."""
		if not any(p.is_all_in for p in self.players):
			self.side_pots = []
			return

		# Get all unique bet amounts
		all_bets = sorted(set(self.round_bets.values()))
		
		prev_amount = 0
		side_pots = []
		
		for bet_amount in all_bets:
			pot_contribution = bet_amount - prev_amount
			if pot_contribution <= 0:
				continue
				
			# Players eligible for this pot level
			eligible_players = [i for i, p in enumerate(self.players)
							  if p.is_active and self.round_bets.get(i, 0) >= bet_amount]
			
			# Calculate pot amount for this level
			pot_amount = pot_contribution * sum(1 for i in range(len(self.players))
											  if self.round_bets.get(i, 0) >= bet_amount)
			
			if pot_amount > 0:
				side_pots.append((pot_amount, eligible_players))
			
			prev_amount = bet_amount
		
		self.side_pots = side_pots
		self.pot = sum(amount for amount, _ in side_pots)