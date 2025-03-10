from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, List
import json
import logging
import asyncio

from ..llm.openrouter import OpenRouterClient
from ..poker_engine.game import Game, Street
from ..poker_engine.player import Player

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount static files
static_path = Path(__file__).parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Store active games
active_games: Dict[str, Game] = {}
active_connections: Dict[str, List[WebSocket]] = {}

# Initialize OpenRouter client
openrouter_client = OpenRouterClient()

async def handle_bot_actions(game: Game, game_id: str):
	"""Handle bot actions when it's their turn."""
	while True:
		await asyncio.sleep(1)  # Small delay for visual feedback
		if game_id not in active_games:
			logger.debug(f"Game {game_id} no longer exists, stopping bot task")
			break
			
		# Don't process bot actions while waiting for next hand
		if game.waiting_for_next_hand:
			await asyncio.sleep(0.5)
			continue
			
		current_player = game.get_active_player()
		if current_player.player_type == "bot" and current_player.is_active:
			logger.debug(f"Bot {current_player.name} taking action in game {game_id}")
			
			# Get the amount needed to call
			to_call = game.current_bet - (game.round_bets.get(game.active_player_idx, 0))
			
			# Simple bot strategy: 
			# - If no bet to call (to_call == 0), then check
			# - Otherwise call any bet
			action = "call"  # Both check and call use the same action type
			logger.debug(f"Bot {current_player.name} decided to {'check' if to_call == 0 else 'call'}")
			
			game.handle_action(action)
			logger.debug(f"Bot {current_player.name} action completed in game {game_id}")
			await broadcast_game_state(game_id)
		else:
			# Add longer sleep when it's not bot's turn to reduce unnecessary checks
			await asyncio.sleep(0.5)


async def broadcast_game_state(game_id: str):
	"""Broadcast the current game state to all connected clients."""
	if game_id not in active_games:
		logger.debug(f"Attempted to broadcast for non-existent game {game_id}")
		return
		
	game = active_games[game_id]
	logger.debug(f"Broadcasting game state for game {game_id}")
	logger.debug(f"Current positions - Dealer: {game.dealer_pos}, SB: {game.small_blind_pos}, BB: {game.big_blind_pos}, Active: {game.active_player_idx}")
	
	# Get showdown results if the hand is complete
	showdown_results = []
	is_showdown = False
	if game.current_street == Street.RIVER and all(game.players_acted.get(i, False) for i, p in enumerate(game.players) if p.is_active):
		is_showdown = True
		showdown_results = game.handle_showdown()
	
	game_state = {
		"community_cards": [str(card) for card in game.community_cards],
		"pot": game.pot,
		"current_street": game.current_street.name,
		"current_bet": game.current_bet,
		"showdown": is_showdown,
		"game_over": game.game_over,
		"waiting_for_next_hand": game.waiting_for_next_hand,
		"players": [{
			"name": p.name,
			"stack": p.stack,
			"bet_amount": p.bet_amount,
			"is_active": p.is_active and i not in game.eliminated_players,
			"hole_cards": [str(card) for card in p.hole_cards],
			"position": i,
			"is_sb": i == game.small_blind_pos,  # Use stored SB position
			"is_bb": i == game.big_blind_pos,    # Use stored BB position
			"is_human": p.player_type == "human",
			"is_active_player": i == game.active_player_idx and i not in game.eliminated_players,
			"is_eliminated": i in game.eliminated_players,
			"is_winner": any(winner_idx == i for winner_idx, _ in showdown_results),
			"amount_won": sum(amount for winner_idx, amount in showdown_results if winner_idx == i),
			"hand_description": p.hand_description if hasattr(p, 'hand_description') and is_showdown else None
		} for i, p in enumerate(game.players)]
	}
	
	if game_id in active_connections:
		connection_count = len(active_connections[game_id])
		logger.debug(f"Broadcasting to {connection_count} connections for game {game_id}")
		for connection in active_connections[game_id]:
			await connection.send_json(game_state)
			logger.debug(f"Game state sent to a connection in game {game_id}")

	# Clean up game if it's over
	if game.game_over:
		logger.debug(f"Game {game_id} is over, cleaning up")
		if game_id in active_games:
			del active_games[game_id]

@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
	await websocket.accept()
	logger.debug(f"New WebSocket connection accepted for game {game_id}")
	
	if game_id not in active_connections:
		active_connections[game_id] = []
	active_connections[game_id].append(websocket)
	logger.debug(f"Total connections for game {game_id}: {len(active_connections[game_id])}")
	
	try:
		bot_task = None
		while True:
			data = await websocket.receive_json()
			logger.debug(f"Received WebSocket data for game {game_id}: {data}")
			game = active_games.get(game_id)
			
			if data["type"] == "start_game":
				logger.debug(f"Starting new game {game_id}")
				# Initialize new game with players
				players = [
					Player(
						name=p["name"],
						stack=data["config"]["stackSize"],
						position=i,
						player_type=p["type"]
					) for i, p in enumerate(data["players"])
				]
				game = Game(players=players)
				active_games[game_id] = game
				game.start_hand()
				logger.debug(f"Game {game_id} initialized with {len(players)} players")
				
				# Start bot action handling task
				if bot_task:
					logger.debug(f"Cancelling existing bot task for game {game_id}")
					bot_task.cancel()
				bot_task = asyncio.create_task(handle_bot_actions(game, game_id))
				logger.debug(f"Started new bot task for game {game_id}")
				
				# Broadcast initial game state
				await broadcast_game_state(game_id)
			
			elif data["type"] == "action" and game:
				if data["action"] == "next_hand" and game.waiting_for_next_hand:
					logger.debug("Starting next hand...")
					# Reactivate all non-eliminated players
					for i, player in enumerate(game.players):
						if i not in game.eliminated_players:
							player.is_active = True
					game.start_next_hand()
					logger.debug("Next hand started, broadcasting state...")
					await broadcast_game_state(game_id)
					# Resume bot actions after next hand starts
					if bot_task:
						bot_task.cancel()
					bot_task = asyncio.create_task(handle_bot_actions(game, game_id))
				elif game.get_active_player().player_type == "human":
					logger.debug(f"Processing human action in game {game_id}: {data['action']}")
					# Handle regular actions
					amount = data.get("amount", None)
					if amount is not None:
						amount = int(amount)
					game.handle_action(data["action"], amount)
					logger.debug(f"Human action processed in game {game_id}")
					await broadcast_game_state(game_id)

				
	except WebSocketDisconnect:
		logger.debug(f"WebSocket disconnected for game {game_id}")
		active_connections[game_id].remove(websocket)
		logger.debug(f"Remaining connections for game {game_id}: {len(active_connections[game_id])}")
		if bot_task:
			logger.debug(f"Cancelling bot task due to disconnect in game {game_id}")
			bot_task.cancel()

@app.get("/")
async def root():
	return FileResponse(str(static_path / "index.html"))

class ChatMessage(BaseModel):
	messages: List[Dict[str, str]]

@app.post("/api/chat")
async def chat(message: ChatMessage):
	try:
		response = await openrouter_client.chat(message.messages)
		return {"response": response}
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))