from enum import IntEnum
from typing import List, Tuple
from collections import Counter
from .card import Card, Rank, Suit

class HandRank(IntEnum):
	HIGH_CARD = 1
	PAIR = 2
	TWO_PAIR = 3
	THREE_OF_KIND = 4
	STRAIGHT = 5
	FLUSH = 6
	FULL_HOUSE = 7
	FOUR_OF_KIND = 8
	STRAIGHT_FLUSH = 9

def evaluate_hand(hole_cards: List[Card], community_cards: List[Card]) -> Tuple[HandRank, List[Card]]:
	"""Evaluate the best 5-card hand from hole cards and community cards."""
	all_cards = hole_cards + community_cards
	
	# Check for straight flush
	flush_cards = get_flush_cards(all_cards)
	if flush_cards:
		straight_flush = get_straight_cards(flush_cards)
		if straight_flush:
			return HandRank.STRAIGHT_FLUSH, straight_flush

	# Check for four of a kind
	four_kind = get_four_of_kind(all_cards)
	if four_kind:
		return HandRank.FOUR_OF_KIND, four_kind

	# Check for full house
	full_house = get_full_house(all_cards)
	if full_house:
		return HandRank.FULL_HOUSE, full_house

	# Check for flush
	if flush_cards:
		return HandRank.FLUSH, flush_cards[:5]

	# Check for straight
	straight = get_straight_cards(all_cards)
	if straight:
		return HandRank.STRAIGHT, straight

	# Check for three of a kind
	three_kind = get_three_of_kind(all_cards)
	if three_kind:
		return HandRank.THREE_OF_KIND, three_kind

	# Check for two pair
	two_pair = get_two_pair(all_cards)
	if two_pair:
		return HandRank.TWO_PAIR, two_pair

	# Check for pair
	pair = get_pair(all_cards)
	if pair:
		return HandRank.PAIR, pair

	# High card
	return HandRank.HIGH_CARD, sorted(all_cards, key=lambda x: x.rank.value, reverse=True)[:5]

def get_flush_cards(cards: List[Card]) -> List[Card]:
	"""Find the highest flush if it exists."""
	suit_groups = {}
	for card in cards:
		if card.suit not in suit_groups:
			suit_groups[card.suit] = []
		suit_groups[card.suit].append(card)
	
	for suit_cards in suit_groups.values():
		if len(suit_cards) >= 5:
			return sorted(suit_cards, key=lambda x: x.rank.value, reverse=True)[:5]
	return []

def get_straight_cards(cards: List[Card]) -> List[Card]:
	"""Find the highest straight if it exists."""
	sorted_cards = sorted(cards, key=lambda x: x.rank.value, reverse=True)
	unique_ranks = sorted(set(card.rank.value for card in sorted_cards), reverse=True)
	
	# Handle Ace-low straight
	if Rank.ACE.value in unique_ranks and all(r in unique_ranks for r in range(2, 6)):
		ace = next(card for card in sorted_cards if card.rank == Rank.ACE)
		low_straight = [ace] + [card for card in sorted_cards if 2 <= card.rank.value <= 5]
		return low_straight[:5]

	# Check for regular straights
	for i in range(len(unique_ranks) - 4):
		if unique_ranks[i] - unique_ranks[i + 4] == 4:
			straight_ranks = unique_ranks[i:i + 5]
			return [next(card for card in sorted_cards if card.rank.value == rank) 
				   for rank in straight_ranks]
	return []

def get_four_of_kind(cards: List[Card]) -> List[Card]:
	"""Find four of a kind if it exists."""
	rank_groups = Counter(card.rank for card in cards)
	for rank, count in rank_groups.items():
		if count == 4:
			four_cards = [card for card in cards if card.rank == rank]
			kicker = next(card for card in sorted(cards, key=lambda x: x.rank.value, reverse=True)
						 if card.rank != rank)
			return four_cards + [kicker]
	return []

def get_full_house(cards: List[Card]) -> List[Card]:
	"""Find full house if it exists."""
	rank_groups = Counter(card.rank for card in cards)
	three_kind = None
	pair = None
	
	# Find highest three of a kind
	for rank, count in rank_groups.items():
		if count >= 3 and (three_kind is None or rank.value > three_kind.value):
			three_kind = rank
	
	# Find highest pair excluding three of a kind rank
	if three_kind:
		for rank, count in rank_groups.items():
			if count >= 2 and rank != three_kind and (pair is None or rank.value > pair.value):
				pair = rank
	
	if three_kind and pair:
		three_cards = [card for card in cards if card.rank == three_kind][:3]
		pair_cards = [card for card in cards if card.rank == pair][:2]
		return three_cards + pair_cards
	return []

def get_three_of_kind(cards: List[Card]) -> List[Card]:
	"""Find three of a kind if it exists."""
	rank_groups = Counter(card.rank for card in cards)
	for rank, count in rank_groups.items():
		if count == 3:
			three_cards = [card for card in cards if card.rank == rank]
			other_cards = sorted([card for card in cards if card.rank != rank],
							   key=lambda x: x.rank.value, reverse=True)[:2]
			return three_cards + other_cards
	return []

def get_two_pair(cards: List[Card]) -> List[Card]:
	"""Find two pair if it exists."""
	rank_groups = Counter(card.rank for card in cards)
	pairs = [(rank, count) for rank, count in rank_groups.items() if count >= 2]
	if len(pairs) >= 2:
		pairs.sort(key=lambda x: x[0].value, reverse=True)
		first_pair = [card for card in cards if card.rank == pairs[0][0]][:2]
		second_pair = [card for card in cards if card.rank == pairs[1][0]][:2]
		kicker = next(card for card in sorted(cards, key=lambda x: x.rank.value, reverse=True)
					 if card.rank != pairs[0][0] and card.rank != pairs[1][0])
		return first_pair + second_pair + [kicker]
	return []

def get_pair(cards: List[Card]) -> List[Card]:
	"""Find highest pair if it exists."""
	rank_groups = Counter(card.rank for card in cards)
	for rank, count in sorted(rank_groups.items(), key=lambda x: x[0].value, reverse=True):
		if count >= 2:
			pair_cards = [card for card in cards if card.rank == rank][:2]
			other_cards = sorted([card for card in cards if card.rank != rank],
							   key=lambda x: x.rank.value, reverse=True)[:3]
			return pair_cards + other_cards
	return []

def compare_hands(hand1: Tuple[HandRank, List[Card]], hand2: Tuple[HandRank, List[Card]]) -> int:
	"""Compare two hands. Returns 1 if hand1 wins, -1 if hand2 wins, 0 if tie."""
	rank1, cards1 = hand1
	rank2, cards2 = hand2
	
	if rank1 != rank2:
		return 1 if rank1 > rank2 else -1
	
	# Compare kickers
	for card1, card2 in zip(cards1, cards2):
		if card1.rank != card2.rank:
			return 1 if card1.rank.value > card2.rank.value else -1
	
	return 0