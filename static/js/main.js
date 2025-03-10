class PokerGame {
	static hasInitializedEventListener = false;
	
	constructor(config) {
		console.log('Initializing PokerGame with config:', config);
		this.config = config;
		this.ws = null;
		this.connectWebSocket();
	}

	connectWebSocket() {
		console.log('Connecting WebSocket...');
		this.ws = new WebSocket(`ws://${window.location.host}/ws/game1`);
		
		this.ws.onopen = () => {
			console.log('WebSocket connected, sending initial game setup');
			this.setupEventListeners();
			
			// Send initial game setup
			const players = [
				{ name: 'Player', type: 'human' },
				...Array(this.config.opponents).fill(0).map((_, i) => ({
					name: `Bot ${i + 1}`,
					type: 'bot'
				}))
			];
			
			const startGameMessage = {
				type: 'start_game',
				players: players,
				config: {
					stackSize: this.config.stackSize,
					smallBlind: this.config.smallBlind,
					difficulty: this.config.difficulty
				}
			};
			console.log('Sending start game message:', startGameMessage);
			this.ws.send(JSON.stringify(startGameMessage));
		};

		this.ws.onmessage = (event) => {
			console.log('Received WebSocket message:', event.data);
			const gameState = JSON.parse(event.data);
			console.log('Parsed game state:', gameState);
			
			// Track blind positions and active player changes
			console.log('Current game state analysis:', {
				activePlayerIndex: gameState.players.findIndex(p => p.is_active_player),
				smallBlindIndex: gameState.players.findIndex(p => p.is_sb),
				bigBlindIndex: gameState.players.findIndex(p => p.is_bb),
				street: gameState.current_street,
				showdown: gameState.showdown,
				waitingForNextHand: gameState.waiting_for_next_hand
			});
			
			this.updateGameState(gameState);
		};

		this.ws.onerror = (error) => {
			console.error('WebSocket error:', error);
		};

		this.ws.onclose = () => {
			console.log('WebSocket connection closed');
		};
	}

	setupEventListeners() {
		console.log('Setting up event listeners');
		document.getElementById('fold').addEventListener('click', () => {
			console.log('Fold button clicked');
			this.sendAction('fold');
		});

		document.getElementById('next-hand').addEventListener('click', () => {
			console.log('Next hand button clicked');
			this.sendAction('next_hand');
			document.getElementById('next-hand').classList.add('hidden');
		});

		// Add new game button listener
		document.getElementById('new-game').addEventListener('click', () => {
			console.log('Starting new game');
			document.getElementById('game-table').classList.add('hidden');
			document.getElementById('game-config').classList.remove('hidden');
			document.getElementById('game-over').classList.add('hidden');
			if (this.ws) {
				this.ws.close();
			}
		});

		document.getElementById('call').addEventListener('click', () => {
			console.log('Call button clicked');
			this.sendAction('call');
		});

		if (!PokerGame.hasInitializedEventListener) {
			PokerGame.hasInitializedEventListener = true;
			
			const raiseBtn = document.getElementById('raise');
			const raiseInput = document.getElementById('raise-amount');
			
			raiseBtn.addEventListener('click', () => {
				console.log('Raise button clicked with amount:', raiseInput.value);
				this.sendAction('raise', { amount: parseInt(raiseInput.value) });
			});

			// Use 'input' event for real-time updates
			raiseInput.addEventListener('input', (e) => {
				const value = parseInt(e.target.value);
				raiseBtn.textContent = `Raise $${value}`;
			});
		}
	}

	sendAction(action, data = {}) {
		const message = JSON.stringify({
			type: 'action',
			action,
			...data
		});
		console.log('Sending action:', message);
		this.ws.send(message);
	}

	updateGameState(gameState) {
		console.log('Updating game state with:', gameState);
		
		// Add debug logging for blind positions
		console.log('Player blind positions:');
		gameState.players.forEach((player, i) => {
			console.log(`Player ${player.name}:`, {
				position: i,
				is_bb: player.is_bb,
				is_sb: player.is_sb,
				is_active: player.is_active_player,
				stack: player.stack
			});
		});

		// Handle game over state
		const gameOverEl = document.getElementById('game-over');
		const gameOverMessageEl = document.getElementById('game-over-message');
		
		if (gameState.game_over) {
			const humanPlayer = gameState.players.find(p => p.is_human);
			const message = humanPlayer && humanPlayer.stack === 0 
				? "Game Over - You've lost all your chips!" 
				: "Game Over!";
			gameOverMessageEl.textContent = message;
			gameOverEl.classList.remove('hidden');
			
			// Disable all action buttons
			document.querySelectorAll('.action-buttons button').forEach(btn => btn.disabled = true);
			document.getElementById('raise-amount').disabled = true;
			return;
		} else {
			gameOverEl.classList.add('hidden');
		}
		
		// Update community cards
		const communityCardsEl = document.querySelector('.community-cards');
		communityCardsEl.innerHTML = gameState.community_cards
			.map(card => {
				const [value, suit] = card.split('');
				const isRedSuit = suit === '♥' || suit === '♦';
				return `<div class="card ${isRedSuit ? 'red-suit' : ''}">${value}${suit}</div>`;
			})
			.join('');

		// Show next hand button when a hand is complete but game isn't over
		const nextHandBtn = document.getElementById('next-hand');
		if (gameState.showdown && !gameState.game_over) {
			nextHandBtn.classList.remove('hidden');
		} else {
			nextHandBtn.classList.add('hidden');
		}
		
		// Update pot
		document.querySelector('.pot').textContent = `Pot: $${gameState.pot}`;
		
		// Update action buttons
		const actionButtons = document.querySelectorAll('.action-buttons button:not(#next-hand)');
		const raiseInput = document.getElementById('raise-amount');
		const humanPlayer = gameState.players.find(p => p.is_human);
		
		// Disable controls during showdown, except next-hand button
		if (gameState.showdown) {
			actionButtons.forEach(btn => btn.disabled = true);
			raiseInput.disabled = true;
		} else if (humanPlayer && humanPlayer.is_active_player) {
			actionButtons.forEach(btn => btn.disabled = false);
			raiseInput.disabled = false;
			
			const currentBet = gameState.current_bet || 0;
			const playerBetAmount = humanPlayer.bet_amount || 0;
			const pot = gameState.pot || 0;
			const maxBet = humanPlayer.stack + playerBetAmount;
			
			// Log variables used in minRaise calculation
			console.log('MinRaise calculation variables:', {
				currentBet,
				smallBlind: this.config.smallBlind,
				doubleCurrentBet: currentBet * 2,
				currentBetPlusBlind: currentBet + this.config.smallBlind
			});
			
			const minRaise = Math.max(currentBet * 2, currentBet + this.config.smallBlind);
			
			console.log('Updating raise slider:', { minRaise, maxBet, pot });
			
			// Update raise input constraints
			raiseInput.min = minRaise;
			raiseInput.max = maxBet;
			
			// Set initial raise value to min(stack, pot/2)
			const defaultRaise = Math.min(humanPlayer.stack, Math.floor(pot/2));
			const initialRaise = Math.max(minRaise, Math.min(defaultRaise, maxBet));
			raiseInput.value = initialRaise;
			
			// Update raise button text immediately
			const raiseBtn = document.getElementById('raise');
			raiseBtn.textContent = `Raise $${initialRaise}`;
			
			// Add pot-based markers
			const markersContainer = document.getElementById('raise-markers');
			const markers = [];
			
			// Calculate pot-based values
			[0.5, 1, 2, 3].forEach(multiplier => {
				const potValue = Math.min(pot * multiplier, maxBet);
				if (potValue > minRaise && potValue < maxBet) {
					// Adjust percentage calculation to account for slider thumb width
					const percentage = ((potValue - minRaise) / (maxBet - minRaise)) * 100;
					const adjustedPosition = percentage + (percentage > 0 ? 0.8 : 0); // Small adjustment to align with thumb center
					console.log(`Marker ${multiplier}x:`, { potValue, minRaise, maxBet, percentage, adjustedPosition });
					markers.push({
						value: potValue,
						label: `${multiplier}x pot`,
						position: Math.min(Math.max(adjustedPosition, 0), 100)
					});
				}
			});
			
			console.log('Setting markers:', markers);
			markersContainer.style.pointerEvents = 'none';
			markersContainer.innerHTML = markers
				.map(marker => `<div class="raise-marker" style="left: ${marker.position}%; cursor: pointer; pointer-events: auto; white-space: nowrap;" data-value="${marker.value}">${marker.label}</div>`)
				.join('');
			
			// Add click handlers to markers
			const markerElements = markersContainer.querySelectorAll('.raise-marker');
			markerElements.forEach(marker => {
				['click', 'touchstart'].forEach(eventType => {
					marker.addEventListener(eventType, (e) => {
						e.preventDefault();
						e.stopPropagation();
						console.log(`Marker ${eventType} event triggered`);
						const value = parseInt(marker.dataset.value);
						if (!isNaN(value)) {
							raiseInput.value = value;
							raiseBtn.textContent = `Raise $${value}`;
							// Dispatch input event to ensure consistency
							raiseInput.dispatchEvent(new Event('input'));
						}
					});
				});
			});
			
			const toCall = currentBet - playerBetAmount;
			const callBtn = document.getElementById('call');
			callBtn.textContent = toCall > 0 ? `Call $${toCall}` : 'Check';
		} else {


			actionButtons.forEach(btn => btn.disabled = true);
			raiseInput.disabled = true;
		}

		// Update players
		const playersEl = document.querySelector('.players');
		playersEl.innerHTML = gameState.players
			.map((player, i) => {
				const position = this.getPlayerPosition(i, gameState.players.length);
				
				// Debug log for each player's state
				console.log(`Player ${player.name} state:`, {
					index: i,
					isActive: player.is_active,
					isActivePlayer: player.is_active_player,
					isSB: player.is_sb,
					isBB: player.is_bb,
					stack: player.stack,
					betAmount: player.bet_amount
				});
				
				// Debug log for each player's state
				console.log(`Player ${player.name} state:`, {
					index: i,
					isActive: player.is_active,
					isActivePlayer: player.is_active_player,
					isSB: player.is_sb,
					isBB: player.is_bb,
					isDealer: i === ((gameState.players.findIndex(p => p.is_sb) - 1 + gameState.players.length) % gameState.players.length),
					stack: player.stack,
					betAmount: player.bet_amount
				});
				
				let positionIndicators = '';
				// Calculate dealer position (one position before small blind)
				const dealerPos = i === ((gameState.players.findIndex(p => p.is_sb) - 1 + gameState.players.length) % gameState.players.length);
				if (dealerPos) {
					positionIndicators += '<div class="dealer-button">D</div>';
				}

				// Add blind indicators after dealer button
				if (player.is_bb) positionIndicators += '<div class="blind-indicator">BB</div>';
				if (player.is_sb) positionIndicators += '<div class="blind-indicator">SB</div>';

				// Show all cards during showdown
				const holeCardsHtml = player.hole_cards
					.map(card => {
						if (player.is_human || gameState.showdown) {
							const [value, suit] = card.split('');
							const isRedSuit = suit === '♥' || suit === '♦';
							return `<div class="card ${player.is_winner ? 'winning-hand' : ''} ${isRedSuit ? 'red-suit' : ''}">${value}${suit}</div>`;
						} else {
							return '<div class="card face-down"></div>';
						}
					})
					.join('');

				const activeClass = player.is_active_player ? 'active-player' : '';
				const handDescription = player.hand_description ? 
					`<div class="hand-description">${player.hand_description}</div>` : '';
				
				// Add pot win animation if player won chips
				let potWinHtml = '';
				if (player.amount_won > 0) {
					potWinHtml = `<div class="pot-win">+$${player.amount_won}</div>`;
				}

				return `
					<div class="player ${activeClass}" style="left: ${position.x}%; top: ${position.y}%">
						${positionIndicators}
						<div>${player.name}</div>
						<div>Stack: $${player.stack}</div>
						${player.bet_amount > 0 ? `<div>Bet: $${player.bet_amount}</div>` : ''}
						<div class="player-cards">
							${holeCardsHtml}
						</div>
						${handDescription}
						${potWinHtml}
					</div>
				`;
			})
			.join('');
	}


	getPlayerPosition(index, totalPlayers) {
		const totalOtherPlayers = totalPlayers - 1;
		
		// Use a wider arc (200 degrees) for better distribution
		const arcAngle = 2 * Math.PI / totalPlayers; // 200 degrees in radians
		const startAngle = Math.PI / 2; // Start from left side
		
		// Calculate position on the arc
		const angle = (index * arcAngle) + startAngle;
		
		// Use different radii for x and y to create an elliptical distribution
		const xRadius = 45;
		const yRadius = 35;
		
		return {
			x: 50 + xRadius * Math.cos(angle),
			y: 50 + yRadius * Math.sin(angle) // Center is moved up to 40% from top
		};
	}
}

// Handle game configuration and initialization
function initializeGameConfig() {
	const startGameBtn = document.getElementById('start-game');
	const gameConfig = document.getElementById('game-config');
	const gameTable = document.getElementById('game-table');

	startGameBtn.addEventListener('click', () => {
		console.log('Start game button clicked');
		const config = {
			stackSize: parseInt(document.getElementById('stack-size').value),
			smallBlind: parseInt(document.getElementById('small-blind').value),
			opponents: parseInt(document.getElementById('opponents').value),
			difficulty: document.getElementById('difficulty').value
		};
		console.log('Game config:', config);

		// Hide config screen and show game table
		gameConfig.classList.add('hidden');
		gameTable.classList.remove('hidden');

		// Initialize the game with config
		new PokerGame(config);
	});
}


// Start configuration when the page loads
window.addEventListener('load', initializeGameConfig);