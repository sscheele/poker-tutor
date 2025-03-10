import os
import httpx
from typing import Dict, List, Optional
from dotenv import load_dotenv
from ..poker_engine.game import Game

load_dotenv()

class OpenRouterClient:
	def __init__(self):
		self.api_key = os.getenv("OPENROUTER_API_KEY")
		if not self.api_key:
			raise ValueError("OPENROUTER_API_KEY not found in environment variables")
		
		self.base_url = "https://openrouter.ai/api/v1"
		self.headers = {
			"Authorization": f"Bearer {self.api_key}",
			"HTTP-Referer": "http://localhost:8000",
		}

	async def chat(self, messages: List[Dict[str, str]], game: Optional[Game] = None) -> str:
		"""Send a chat message to the LLM with message history and optional game state.
		
		Args:
			messages: List of message dictionaries with 'role' and 'content' keys
			game: Optional Game object for providing game state context
		"""
		system_message = {
			"role": "system",
			"content": "You are a poker coach and tutor. Help users understand poker concepts, strategy, and answer their questions about the game."
		}

		# If game is provided, modify the last user message with game context
		if game and messages:
			last_user_message = messages[-1]["content"]
			prompt = self._create_preplay_prompt(game)
			print(prompt)
			messages[-1]["content"] = prompt + last_user_message
		
		async with httpx.AsyncClient() as client:
			response = await client.post(
				f"{self.base_url}/chat/completions",
				headers=self.headers,
				json={
					"model": "anthropic/claude-3.5-sonnet",
					"messages": [system_message] + messages
				}
			)
			
			response.raise_for_status()
			return response.json()["choices"][0]["message"]["content"]

	async def analyze_play(
		self,
		player_action: Dict,
		game_state: Dict,
		optimal_play: Dict
	) -> str:
		"""Analyze a player's action and provide feedback."""
		prompt = self._create_analysis_prompt(player_action, game_state, optimal_play)
		
		async with httpx.AsyncClient() as client:
			response = await client.post(
				f"{self.base_url}/chat/completions",
				headers=self.headers,
				json={
					"model": "anthropic/claude-3-opus",
					"messages": [
						{
							"role": "system",
							"content": "You are a poker coach analyzing player decisions. Provide clear, concise feedback focusing on strategic concepts and mathematical reasoning."
						},
						{
							"role": "user",
							"content": prompt
						}
					]
				}
			)
			
			response.raise_for_status()
			return response.json()["choices"][0]["message"]["content"]

	def _get_player_position(self, game: Game) -> str:
		"""Determine the player's position name based on game state."""
		active_players = sum(1 for p in game.players if p.is_active)
		position_names = {
			game.small_blind_pos: "Small Blind (Out of Position)", 
			game.big_blind_pos: "Big Blind (Out of Position)",
			(game.big_blind_pos + 1) % len(game.players): "UTG (Under the Gun)",
		}
		
		# For 6+ players, add more detailed positions
		if active_players >= 6:
			position_names[(game.big_blind_pos + 2) % len(game.players)] = "UTG+1"
			position_names[(game.big_blind_pos + 3) % len(game.players)] = "MP (Middle Position)"
			position_names[(game.dealer_pos - 1) % len(game.players)] = "HJ (Hijack)"
			position_names[(game.dealer_pos) % len(game.players)] = "BTN (Button, In Position)"
		else:
			# For shorter handed games
			position_names[game.dealer_pos] = "BTN (Button, In Position)"
			
		player_position = position_names.get(game.active_player_idx)
		if not player_position:
			# If position not explicitly named, determine if in position or out of position
			if (game.active_player_idx - game.dealer_pos) % len(game.players) <= len(game.players) // 2:
				player_position = "Late Position (In Position)"
			else:
				player_position = "Early Position (Out of Position)"
		return player_position

	def _create_preplay_prompt(
		self,
		game: Game,
		optimal_play: Optional[Dict] = None
	) -> str:
		"""Create a prompt for analyzing the current game state before playing."""
		active_player = game.get_active_player()
		player_position = self._get_player_position(game)
		
		# Get betting history for current street
		current_street_history = next((h for h in game.hand_history if h['street'] == game.current_street.name), None)
		betting_history = current_street_history['actions'] if current_street_history else []
		
		prompt = f"""
		Respond to the user's query about the following poker situation:
		
		Game State:
		- Street: {game.current_street.name}
		- Pot: ${game.pot}
		- Community Cards: {', '.join(str(card) for card in game.community_cards)}
		- Position: {player_position}
		- Active Players: {sum(1 for p in game.players if p.is_active)}
		- Stack Sizes: {', '.join(f'Player {i}: ${p.stack}' for i, p in enumerate(game.players) if p.is_active)}
		- Current Bet: ${game.current_bet}
		- Previous Actions: {[f"{a['action']}({a['amount']})" if 'amount' in a else a['action'] for a in betting_history]}
		
		Player Info:
		- Hand: {', '.join(str(card) for card in active_player.hole_cards)}
		- Stack: ${active_player.stack}
		"""
		
		if optimal_play:
			prompt += f"""
			
			Optimal Play:
			- Action: {optimal_play['action']}
			- Amount: ${optimal_play.get('amount', 0)}
			"""

		prompt += "\nUser message: "
		
		return prompt

	def _create_analysis_prompt(
		self,
		game: Game,
		player_action: Dict,
		optimal_play: Dict
	) -> str:
		"""Create a prompt for analyzing the player's action."""
		active_player = game.get_active_player()
		player_position = self._get_player_position(game)

		
		# Get betting history for current street
		current_street_history = next((h for h in game.hand_history if h['street'] == game.current_street.name), None)
		betting_history = current_street_history['actions'] if current_street_history else []
		
		return f"""
		Analyze this poker hand:
		
		Game State:
		- Street: {game.current_street.name}
		- Pot: ${game.pot}
		- Community Cards: {', '.join(str(card) for card in game.community_cards)}
		- Position: {player_position}
		- Active Players: {sum(1 for p in game.players if p.is_active)}
		- Stack Sizes: {', '.join(f'Player {i}: ${p.stack}' for i, p in enumerate(game.players) if p.is_active)}
		- Current Bet: ${game.current_bet}
		- Previous Actions: {[f"{a['action']}({a['amount']})" if 'amount' in a else a['action'] for a in betting_history]}
		
		Player Info:
		- Hand: {', '.join(str(card) for card in active_player.hole_cards)}
		- Stack: ${active_player.stack}
		
		Player Action:
		- Action: {player_action['action']}
		- Amount: ${player_action.get('amount', 0)}
		
		Optimal Play:
		- Action: {optimal_play['action']}
		- Amount: ${optimal_play.get('amount', 0)}
		
		Explain:
		1. Whether the player's decision was optimal
		2. The key strategic concepts behind the optimal play
		3. Any mathematical considerations (pot odds, implied odds, etc.)
		4. How position and stack sizes influenced the decision
		"""