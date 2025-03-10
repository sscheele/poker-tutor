import os
import httpx
from typing import Dict, List
from dotenv import load_dotenv

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

	async def chat(self, messages: List[Dict[str, str]]) -> str:
		"""Send a chat message to the LLM with message history.
		
		Args:
			messages: List of message dictionaries with 'role' and 'content' keys
		"""
		system_message = {
			"role": "system",
			"content": "You are a poker coach and tutor. Help users understand poker concepts, strategy, and answer their questions about the game."
		}
		
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

	def _create_analysis_prompt(
		self,
		player_action: Dict,
		game_state: Dict,
		optimal_play: Dict
	) -> str:
		"""Create a prompt for analyzing the player's action."""
		return f"""
		Analyze this poker hand:
		
		Game State:
		- Street: {game_state['current_street']}
		- Pot: ${game_state['pot']}
		- Community Cards: {', '.join(game_state['community_cards'])}
		
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
		"""