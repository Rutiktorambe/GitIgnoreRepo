(function () {
    const roomCodeLabel = document.getElementById("roomCodeLabel");
    const copyRoomCodeButton = document.getElementById("copyRoomCodeButton");
    const connectionDot = document.getElementById("connectionDot");
    const connectionText = document.getElementById("connectionText");
    const roundLabel = document.getElementById("roundLabel");
    const buzzerStateLabel = document.getElementById("buzzerStateLabel");
    const buzzerButton = document.getElementById("buzzerButton");
    const roomStatus = document.getElementById("roomStatus");
    const hostControls = document.getElementById("hostControls");
    const resetRoundButton = document.getElementById("resetRoundButton");
    const playersList = document.getElementById("playersList");
    const scoreboardList = document.getElementById("scoreboardList");
    const playerCount = document.getElementById("playerCount");
    const joinOverlay = document.getElementById("joinOverlay");
    const joinNameForm = document.getElementById("joinNameForm");
    const joinRoomTitle = document.getElementById("joinRoomTitle");
    const playerNameInput = document.getElementById("playerNameInput");
    const joinNameButton = document.getElementById("joinNameButton");
    const joinStatus = document.getElementById("joinStatus");
    const winnerModal = document.getElementById("winnerModal");
    const winnerText = document.getElementById("winnerText");
    const closeWinnerButton = document.getElementById("closeWinnerButton");
    const serverSetup = document.getElementById("serverSetup");
    const serverUrlInput = document.getElementById("serverUrlInput");

    const params = new URLSearchParams(window.location.search);
    const state = {
        roomCode: String(params.get("code") || "").trim().toUpperCase(),
        backendUrl: getBackendUrl(),
        hostToken: "",
        playerId: "",
        playerName: "",
        isHost: false,
        isConnected: false,
        isJoined: false,
        isBuzzing: false,
        round: 1,
        winner: null,
        lastLocalBuzzAt: 0,
    };

    let socket = null;
    let audioContext = null;

    function normalizeBackendUrl(value) {
        const rawValue = String(value || "").trim();
        if (!rawValue) {
            return "";
        }
        try {
            const url = new URL(rawValue);
            return url.origin;
        } catch {
            return "";
        }
    }

    function getBackendUrl() {
        const queryUrl = normalizeBackendUrl(params.get("server") || params.get("backend"));
        if (queryUrl) {
            localStorage.setItem("buzzer_backend_url", queryUrl);
            return queryUrl;
        }
        const storedUrl = normalizeBackendUrl(localStorage.getItem("buzzer_backend_url"));
        if (storedUrl) {
            return storedUrl;
        }
        if (["localhost", "127.0.0.1", ""].includes(window.location.hostname)) {
            return "http://localhost:5000";
        }
        return "";
    }

    function savedPlayerKey() {
        return `buzzer_player_${state.roomCode}`;
    }

    function loadSavedSession() {
        state.hostToken = localStorage.getItem(`buzzer_host_${state.roomCode}`) || "";
        try {
            const saved = JSON.parse(localStorage.getItem(savedPlayerKey()) || "{}");
            state.playerId = saved.playerId || "";
            state.playerName = saved.playerName || "";
            playerNameInput.value = state.playerName;
        } catch {
            state.playerId = "";
            state.playerName = "";
        }
    }

    function savePlayerSession() {
        localStorage.setItem(
            savedPlayerKey(),
            JSON.stringify({ playerId: state.playerId, playerName: state.playerName })
        );
    }

    function setConnectionState(status, text) {
        connectionDot.classList.remove("online", "offline");
        if (status) {
            connectionDot.classList.add(status);
        }
        connectionText.textContent = text;
    }

    function setRoomStatus(message, type) {
        roomStatus.textContent = message || "";
        roomStatus.classList.toggle("error", type === "error");
        roomStatus.classList.toggle("success", type === "success");
    }

    function setJoinStatus(message, type) {
        joinStatus.textContent = message || "";
        joinStatus.classList.toggle("error", type === "error");
        joinStatus.classList.toggle("success", type === "success");
    }

    function setButtonLoading(button, isLoading) {
        button.disabled = isLoading;
        button.classList.toggle("is-loading", isLoading);
    }

    function showServerSetup(message) {
        serverSetup.classList.remove("hidden");
        serverUrlInput.value = state.backendUrl || "";
        setConnectionState("offline", "Backend URL required");
        if (message) {
            setJoinStatus(message, "error");
        }
    }

    function ensureAudioContext() {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) {
            return null;
        }
        if (!audioContext) {
            audioContext = new AudioContextClass();
        }
        if (audioContext.state === "suspended") {
            audioContext.resume();
        }
        return audioContext;
    }

    function playTone(frequency, startTime, duration, gainValue) {
        const context = ensureAudioContext();
        if (!context) {
            return;
        }
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(frequency, startTime);
        gain.gain.setValueAtTime(0.0001, startTime);
        gain.gain.exponentialRampToValueAtTime(gainValue, startTime + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(startTime);
        oscillator.stop(startTime + duration + 0.02);
    }

    function playBellSound() {
        const context = ensureAudioContext();
        if (!context) {
            return;
        }
        const now = context.currentTime;
        playTone(740, now, 0.28, 0.22);
        playTone(980, now + 0.04, 0.24, 0.12);
    }

    function playWinnerSound() {
        const context = ensureAudioContext();
        if (!context) {
            return;
        }
        const now = context.currentTime;
        playTone(523.25, now, 0.16, 0.14);
        playTone(659.25, now + 0.14, 0.16, 0.14);
        playTone(783.99, now + 0.28, 0.34, 0.18);
    }

    function updateBuzzerState() {
        const canBuzz = state.isConnected && state.isJoined && !state.winner && !state.isBuzzing;
        buzzerButton.disabled = !canBuzz;

        if (!state.isJoined) {
            buzzerStateLabel.textContent = "Join to enable buzzer";
        } else if (!state.isConnected) {
            buzzerStateLabel.textContent = "Reconnecting";
        } else if (state.winner) {
            buzzerStateLabel.textContent = `${state.winner.name} clicked first`;
        } else if (state.isBuzzing) {
            buzzerStateLabel.textContent = "Submitting buzz";
        } else {
            buzzerStateLabel.textContent = "Buzzer armed";
        }

        hostControls.classList.toggle("hidden", !state.isHost);
        resetRoundButton.disabled = !state.isConnected || !state.isHost;
    }

    function renderPlayers(players) {
        const connectedPlayers = players.filter((player) => player.isConnected);
        playerCount.textContent = `${connectedPlayers.length} online`;
        playersList.innerHTML = "";

        if (!connectedPlayers.length) {
            const empty = document.createElement("li");
            empty.className = "empty-list";
            empty.textContent = "No players online yet.";
            playersList.appendChild(empty);
            return;
        }

        connectedPlayers.forEach((player) => {
            const item = document.createElement("li");
            item.className = "player-item";

            const avatar = document.createElement("span");
            avatar.className = "player-avatar";
            avatar.textContent = player.name.slice(0, 1).toUpperCase();

            const name = document.createElement("span");
            name.className = "player-name";
            name.textContent = player.name;

            const badge = document.createElement("span");
            badge.className = "host-badge";
            badge.textContent = player.isHost ? "Host" : "";

            item.append(avatar, name, badge);
            playersList.appendChild(item);
        });
    }

    function renderScoreboard(scoreboard) {
        scoreboardList.innerHTML = "";

        if (!scoreboard.length) {
            const empty = document.createElement("li");
            empty.className = "empty-list";
            empty.textContent = "Scores appear after the first buzz.";
            scoreboardList.appendChild(empty);
            return;
        }

        scoreboard.forEach((player, index) => {
            const item = document.createElement("li");
            item.className = "score-item";

            const rank = document.createElement("span");
            rank.className = "score-rank";
            rank.textContent = String(index + 1);

            const name = document.createElement("span");
            name.className = "score-name";
            name.textContent = player.name;

            const wins = document.createElement("span");
            wins.className = "score-wins";
            wins.textContent = `${player.wins} win${player.wins === 1 ? "" : "s"}`;

            item.append(rank, name, wins);
            scoreboardList.appendChild(item);
        });
    }

    function applyRoomState(roomState) {
        if (!roomState) {
            return;
        }
        state.round = roomState.round || 1;
        state.winner = roomState.winner || null;
        roundLabel.textContent = `Round ${state.round}`;
        renderPlayers(roomState.players || []);
        renderScoreboard(roomState.scoreboard || []);
        updateBuzzerState();
    }

    function showWinner(winner) {
        if (!winner) {
            return;
        }
        winnerText.textContent = `🏆 ${winner.name} clicked first!`;
        winnerModal.classList.remove("hidden");
    }

    function hideWinner() {
        winnerModal.classList.add("hidden");
    }

    function connectSocket() {
        if (!state.backendUrl) {
            showServerSetup("Paste your Render backend URL to connect this room.");
            return;
        }

        setConnectionState("", "Connecting...");
        socket = io(state.backendUrl, {
            transports: ["websocket", "polling"],
            reconnection: true,
            reconnectionAttempts: Infinity,
            timeout: 8000,
        });

        socket.on("connect", function () {
            state.isConnected = true;
            setConnectionState("online", "Connected");
            setJoinStatus("");
            setRoomStatus("");
            updateBuzzerState();
            if (state.playerName) {
                joinRoom(true);
            }
        });

        socket.on("disconnect", function () {
            state.isConnected = false;
            setConnectionState("offline", "Reconnecting...");
            updateBuzzerState();
        });

        socket.on("connect_error", function () {
            state.isConnected = false;
            setConnectionState("offline", "Connection failed");
            showServerSetup("Could not reach the backend. Check the URL and CORS settings.");
            updateBuzzerState();
        });

        socket.on("player_joined", function (roomState) {
            applyRoomState(roomState);
        });

        socket.on("scoreboard_update", function (payload) {
            renderScoreboard((payload && payload.scoreboard) || []);
        });

        socket.on("winner_selected", function (payload) {
            const winner = payload && payload.winner;
            state.winner = winner || null;
            state.round = payload && payload.round ? payload.round : state.round;
            roundLabel.textContent = `Round ${state.round}`;
            if (Date.now() - state.lastLocalBuzzAt > 700) {
                playBellSound();
            }
            playWinnerSound();
            showWinner(winner);
            updateBuzzerState();
        });

        socket.on("reset_round", function (payload) {
            state.winner = null;
            state.round = payload && payload.round ? payload.round : state.round + 1;
            state.isBuzzing = false;
            roundLabel.textContent = `Round ${state.round}`;
            hideWinner();
            setRoomStatus("Round reset. Buzzer is live.", "success");
            updateBuzzerState();
        });
    }

    function joinRoom(isReconnect) {
        if (!socket || !state.isConnected) {
            setJoinStatus("Connecting to backend...", "error");
            return;
        }

        const playerName = (state.playerName || playerNameInput.value).trim();
        if (!playerName) {
            setJoinStatus("Enter your name before joining.", "error");
            return;
        }

        if (!isReconnect) {
            ensureAudioContext();
            setButtonLoading(joinNameButton, true);
            setJoinStatus("Joining room...");
        }

        socket.timeout(10000).emit(
            "join_room",
            {
                roomCode: state.roomCode,
                name: playerName,
                playerId: state.playerId,
                hostToken: state.hostToken,
            },
            function (error, response) {
                setButtonLoading(joinNameButton, false);
                if (error) {
                    setJoinStatus("The backend did not respond. It may still be waking up.", "error");
                    updateBuzzerState();
                    return;
                }
                if (!response || !response.ok) {
                    setJoinStatus(response && response.error ? response.error : "Could not join room.", "error");
                    updateBuzzerState();
                    return;
                }

                state.playerId = response.player.id;
                state.playerName = response.player.name;
                state.isHost = Boolean(response.isHost);
                state.isJoined = true;
                savePlayerSession();
                joinOverlay.classList.add("hidden");
                setJoinStatus("");
                setRoomStatus(state.isHost ? "Host controls enabled." : "Ready when the round opens.", "success");
                applyRoomState(response.state);
            }
        );
    }

    function buzz() {
        if (!socket || !state.isConnected || !state.isJoined || state.winner) {
            updateBuzzerState();
            return;
        }

        state.isBuzzing = true;
        state.lastLocalBuzzAt = Date.now();
        setRoomStatus("Buzz submitted...");
        updateBuzzerState();
        playBellSound();

        socket.timeout(7000).emit(
            "buzz",
            {
                roomCode: state.roomCode,
                playerId: state.playerId,
            },
            function (error, response) {
                state.isBuzzing = false;
                if (error) {
                    setRoomStatus("The backend did not confirm your buzz. Try again if the round is still open.", "error");
                    updateBuzzerState();
                    return;
                }
                if (!response || !response.ok) {
                    setRoomStatus(response && response.error ? response.error : "Buzz was not accepted.", "error");
                }
                updateBuzzerState();
            }
        );
    }

    function resetRound() {
        if (!socket || !state.isHost) {
            return;
        }
        resetRoundButton.disabled = true;
        setRoomStatus("Resetting round...");
        socket.timeout(10000).emit(
            "reset_round",
            {
                roomCode: state.roomCode,
                hostToken: state.hostToken,
            },
            function (error, response) {
                resetRoundButton.disabled = false;
                if (error) {
                    setRoomStatus("The backend did not respond to the reset request.", "error");
                    updateBuzzerState();
                    return;
                }
                if (!response || !response.ok) {
                    setRoomStatus(response && response.error ? response.error : "Could not reset round.", "error");
                    updateBuzzerState();
                    return;
                }
                applyRoomState(response.state);
            }
        );
    }

    function copyRoomCode() {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(state.roomCode).then(function () {
                setRoomStatus("Room code copied.", "success");
            });
            return;
        }

        const helper = document.createElement("input");
        helper.value = state.roomCode;
        document.body.appendChild(helper);
        helper.select();
        document.execCommand("copy");
        helper.remove();
        setRoomStatus("Room code copied.", "success");
    }

    joinNameForm.addEventListener("submit", function (event) {
        event.preventDefault();
        state.playerName = playerNameInput.value.trim();
        joinRoom(false);
    });

    buzzerButton.addEventListener("click", buzz);
    resetRoundButton.addEventListener("click", resetRound);
    copyRoomCodeButton.addEventListener("click", copyRoomCode);
    closeWinnerButton.addEventListener("click", hideWinner);

    serverSetup.addEventListener("submit", function (event) {
        event.preventDefault();
        const nextBackendUrl = normalizeBackendUrl(serverUrlInput.value);
        if (!nextBackendUrl) {
            setJoinStatus("Enter a valid backend URL.", "error");
            return;
        }
        localStorage.setItem("buzzer_backend_url", nextBackendUrl);
        state.backendUrl = nextBackendUrl;
        serverSetup.classList.add("hidden");
        if (socket) {
            socket.disconnect();
        }
        connectSocket();
    });

    if (!/^[A-Z0-9]{6}$/.test(state.roomCode)) {
        window.location.href = "index.html";
        return;
    }

    roomCodeLabel.textContent = state.roomCode;
    joinRoomTitle.textContent = `Room ${state.roomCode}`;
    loadSavedSession();
    updateBuzzerState();
    connectSocket();
})();
