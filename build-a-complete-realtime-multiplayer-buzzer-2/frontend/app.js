(function () {
    const createRoomButton = document.getElementById("createRoomButton");
    const joinRoomForm = document.getElementById("joinRoomForm");
    const roomCodeInput = document.getElementById("roomCodeInput");
    const statusMessage = document.getElementById("homeStatus");
    const connectionDot = document.getElementById("connectionDot");
    const connectionText = document.getElementById("connectionText");
    const serverSetup = document.getElementById("serverSetup");
    const serverUrlInput = document.getElementById("serverUrlInput");

    let socket = null;
    let backendUrl = getBackendUrl();

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
        const params = new URLSearchParams(window.location.search);
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

    function setConnectionState(state, text) {
        connectionDot.classList.remove("online", "offline");
        if (state) {
            connectionDot.classList.add(state);
        }
        connectionText.textContent = text;
    }

    function setStatus(message, type) {
        statusMessage.textContent = message || "";
        statusMessage.classList.toggle("error", type === "error");
        statusMessage.classList.toggle("success", type === "success");
    }

    function setButtonLoading(button, isLoading) {
        button.disabled = isLoading;
        button.classList.toggle("is-loading", isLoading);
    }

    function showServerSetup() {
        serverSetup.classList.remove("hidden");
        serverUrlInput.value = backendUrl || "";
        setConnectionState("offline", "Backend URL required");
        setStatus("Paste your Render backend URL to connect this frontend.", "error");
    }

    function connectSocket() {
        if (!backendUrl) {
            showServerSetup();
            return;
        }

        setConnectionState("", "Connecting...");
        socket = io(backendUrl, {
            transports: ["websocket", "polling"],
            reconnection: true,
            reconnectionAttempts: Infinity,
            timeout: 8000,
        });

        socket.on("connect", function () {
            setConnectionState("online", "Connected");
            setStatus("");
        });

        socket.on("disconnect", function () {
            setConnectionState("offline", "Reconnecting...");
        });

        socket.on("connect_error", function () {
            setConnectionState("offline", "Connection failed");
            setStatus("Could not reach the backend. Check the backend URL and CORS origins.", "error");
            serverSetup.classList.remove("hidden");
            serverUrlInput.value = backendUrl;
        });
    }

    function roomUrl(roomCode, isHost) {
        const url = new URL("room.html", window.location.href);
        url.searchParams.set("code", roomCode);
        url.searchParams.set("server", backendUrl);
        if (isHost) {
            url.searchParams.set("host", "1");
        }
        return url.toString();
    }

    createRoomButton.addEventListener("click", function () {
        if (!socket || !socket.connected || !backendUrl) {
            showServerSetup();
            setStatus("Backend is not connected yet. Try again in a moment.", "error");
            return;
        }

        setButtonLoading(createRoomButton, true);
        setStatus("Creating room...");

        socket.timeout(10000).emit("create_room", {}, function (error, response) {
            setButtonLoading(createRoomButton, false);
            if (error) {
                setStatus("The backend did not respond. It may still be waking up.", "error");
                return;
            }
            if (!response || !response.ok) {
                setStatus(response && response.error ? response.error : "Could not create room.", "error");
                return;
            }

            localStorage.setItem(`buzzer_host_${response.roomCode}`, response.hostToken);
            setStatus("Room created. Redirecting...", "success");
            window.location.href = roomUrl(response.roomCode, true);
        });
    });

    joinRoomForm.addEventListener("submit", function (event) {
        event.preventDefault();
        const roomCode = roomCodeInput.value.trim().toUpperCase();
        if (!/^[A-Z0-9]{6}$/.test(roomCode)) {
            setStatus("Enter a valid 6-character room code.", "error");
            return;
        }
        if (!backendUrl) {
            showServerSetup();
            return;
        }
        window.location.href = roomUrl(roomCode, false);
    });

    roomCodeInput.addEventListener("input", function () {
        roomCodeInput.value = roomCodeInput.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
    });

    serverSetup.addEventListener("submit", function (event) {
        event.preventDefault();
        const nextBackendUrl = normalizeBackendUrl(serverUrlInput.value);
        if (!nextBackendUrl) {
            setStatus("Enter a valid backend URL.", "error");
            return;
        }
        localStorage.setItem("buzzer_backend_url", nextBackendUrl);
        backendUrl = nextBackendUrl;
        serverSetup.classList.add("hidden");
        if (socket) {
            socket.disconnect();
        }
        connectSocket();
    });

    connectSocket();
})();
