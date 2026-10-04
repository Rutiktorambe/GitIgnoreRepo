import os
import re
import secrets
import string
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room as socket_join_room
from supabase import create_client


load_dotenv()

ROOM_CODE_PATTERN = re.compile(r"^[A-Z0-9]{6}$")
ROOM_CODE_ALPHABET = string.ascii_uppercase + string.digits
MAX_NAME_LENGTH = 32

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))


def parse_allowed_origins():
    raw_origins = os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000,http://127.0.0.1:3000",
    )
    if raw_origins.strip() == "*":
        return "*"
    return [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]


ALLOWED_ORIGINS = parse_allowed_origins()
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

socketio = SocketIO(
    app,
    cors_allowed_origins=ALLOWED_ORIGINS,
    async_mode=os.getenv("SOCKETIO_ASYNC_MODE", "eventlet"),
    ping_timeout=30,
    ping_interval=12,
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

supabase = None
database_config_error = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    database_config_error = (
        "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
    )

room_locks = {}
room_locks_guard = Lock()
sid_registry = {}
sid_registry_guard = Lock()


class PublicError(Exception):
    """Error message that is safe to send back to browser clients."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def db():
    if supabase is None:
        raise PublicError(database_config_error)
    return supabase


def get_room_lock(room_code):
    with room_locks_guard:
        if room_code not in room_locks:
            room_locks[room_code] = Lock()
        return room_locks[room_code]


def validate_room_code(room_code):
    code = str(room_code or "").strip().upper()
    if not ROOM_CODE_PATTERN.match(code):
        raise PublicError("Enter a valid 6-character room code.")
    return code


def clean_player_name(name):
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", str(name or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise PublicError("Enter your name before joining.")
    if len(cleaned) > MAX_NAME_LENGTH:
        cleaned = cleaned[:MAX_NAME_LENGTH].rstrip()
    return cleaned


def validate_uuid(value):
    if not value:
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


def public_failure(error, fallback="Something went wrong. Please try again."):
    if isinstance(error, PublicError):
        return {"ok": False, "error": str(error)}
    app.logger.exception(fallback)
    return {"ok": False, "error": fallback}


def find_room_by_code(room_code):
    response = (
        db()
        .table("rooms")
        .select("*")
        .eq("code", room_code)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def find_player(player_id, room_id):
    valid_player_id = validate_uuid(player_id)
    if not valid_player_id:
        return None
    response = (
        db()
        .table("players")
        .select("*")
        .eq("id", valid_player_id)
        .eq("room_id", room_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def generate_unique_room_code():
    for _ in range(20):
        code = "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(6))
        if find_room_by_code(code) is None:
            return code
    raise PublicError("Could not generate a room code. Please try again.")


def ensure_score_row(room_id, player_id):
    response = (
        db()
        .table("scores")
        .select("id,wins")
        .eq("player_id", player_id)
        .limit(1)
        .execute()
    )
    if response.data:
        return int(response.data[0].get("wins") or 0)
    db().table("scores").insert(
        {"room_id": room_id, "player_id": player_id, "wins": 0}
    ).execute()
    return 0


def increment_score(room_id, player_id):
    response = (
        db()
        .table("scores")
        .select("id,wins")
        .eq("player_id", player_id)
        .limit(1)
        .execute()
    )
    if response.data:
        score_id = response.data[0]["id"]
        new_wins = int(response.data[0].get("wins") or 0) + 1
        db().table("scores").update(
            {"wins": new_wins, "updated_at": utc_now()}
        ).eq("id", score_id).execute()
        return new_wins

    db().table("scores").insert(
        {"room_id": room_id, "player_id": player_id, "wins": 1}
    ).execute()
    return 1


def fetch_players(room_id):
    response = (
        db()
        .table("players")
        .select("id,name,is_host,is_connected,joined_at,last_seen")
        .eq("room_id", room_id)
        .order("joined_at")
        .execute()
    )
    return response.data or []


def fetch_scores(room_id):
    response = (
        db()
        .table("scores")
        .select("player_id,wins")
        .eq("room_id", room_id)
        .execute()
    )
    return {row["player_id"]: int(row.get("wins") or 0) for row in response.data or []}


def serialize_player(player, wins=0):
    return {
        "id": player["id"],
        "name": player["name"],
        "isHost": bool(player.get("is_host")),
        "isConnected": bool(player.get("is_connected")),
        "wins": int(wins or 0),
    }


def build_room_state(room):
    players = fetch_players(room["id"])
    scores = fetch_scores(room["id"])

    serialized_players = [
        serialize_player(player, scores.get(player["id"], 0)) for player in players
    ]
    scoreboard = sorted(
        serialized_players,
        key=lambda player: (-player["wins"], player["name"].lower()),
    )

    winner = None
    winner_id = room.get("current_winner_player_id")
    if winner_id:
        winner = next((player for player in serialized_players if player["id"] == winner_id), None)

    return {
        "roomCode": room["code"],
        "round": int(room.get("current_round") or 1),
        "winner": winner,
        "buzzerLocked": winner is not None,
        "players": serialized_players,
        "scoreboard": scoreboard,
    }


def emit_player_and_score_updates(room_code):
    room = find_room_by_code(room_code)
    if not room:
        return None
    state = build_room_state(room)
    socketio.emit("player_joined", state, room=room_code)
    socketio.emit(
        "scoreboard_update",
        {"roomCode": room_code, "scoreboard": state["scoreboard"]},
        room=room_code,
    )
    return state


@app.get("/")
def index():
    return jsonify(
        {
            "ok": True,
            "service": "Realtime Multiplayer Buzzer API",
            "socket": "/socket.io",
        }
    )


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "databaseConfigured": supabase is not None,
            "allowedOrigins": ALLOWED_ORIGINS,
        }
    )


@app.get("/api/rooms/<room_code>")
def get_room(room_code):
    try:
        code = validate_room_code(room_code)
        room = find_room_by_code(code)
        if not room:
            return jsonify({"ok": False, "error": "Room not found."}), 404
        return jsonify({"ok": True, "state": build_room_state(room)})
    except Exception as error:
        response = public_failure(error, "Could not load room.")
        return jsonify(response), 400


@socketio.on("create_room")
def handle_create_room(payload=None):
    try:
        code = generate_unique_room_code()
        host_token = secrets.token_urlsafe(32)
        response = (
            db()
            .table("rooms")
            .insert({"code": code, "host_token": host_token})
            .execute()
        )
        if not response.data:
            raise PublicError("Could not create room. Please try again.")
        return {"ok": True, "roomCode": code, "hostToken": host_token}
    except Exception as error:
        return public_failure(error, "Could not create room.")


@socketio.on("join_room")
def handle_join_room(payload):
    try:
        payload = payload or {}
        room_code = validate_room_code(payload.get("roomCode"))
        player_name = clean_player_name(payload.get("name"))
        requested_player_id = validate_uuid(payload.get("playerId"))
        host_token = str(payload.get("hostToken") or "")

        room = find_room_by_code(room_code)
        if not room:
            raise PublicError("Room not found.")

        is_host = bool(host_token and secrets.compare_digest(host_token, room["host_token"]))
        now = utc_now()
        player = find_player(requested_player_id, room["id"]) if requested_player_id else None

        if player:
            updates = {
                "name": player_name,
                "socket_sid": request.sid,
                "is_connected": True,
                "last_seen": now,
            }
            if is_host or player.get("is_host"):
                updates["is_host"] = True
            response = (
                db()
                .table("players")
                .update(updates)
                .eq("id", player["id"])
                .eq("room_id", room["id"])
                .execute()
            )
            player = response.data[0]
        else:
            response = (
                db()
                .table("players")
                .insert(
                    {
                        "room_id": room["id"],
                        "name": player_name,
                        "socket_sid": request.sid,
                        "is_host": is_host,
                        "is_connected": True,
                        "joined_at": now,
                        "last_seen": now,
                    }
                )
                .execute()
            )
            player = response.data[0]

        ensure_score_row(room["id"], player["id"])
        socket_join_room(room_code)

        with sid_registry_guard:
            sid_registry[request.sid] = {
                "roomCode": room_code,
                "playerId": player["id"],
            }

        state = emit_player_and_score_updates(room_code)
        return {
            "ok": True,
            "player": serialize_player(player, ensure_score_row(room["id"], player["id"])),
            "isHost": bool(player.get("is_host")),
            "state": state,
        }
    except Exception as error:
        return public_failure(error, "Could not join room.")


@socketio.on("buzz")
def handle_buzz(payload):
    try:
        payload = payload or {}
        room_code = validate_room_code(payload.get("roomCode"))
        player_id = validate_uuid(payload.get("playerId"))
        if not player_id:
            raise PublicError("Join the room before buzzing.")

        lock = get_room_lock(room_code)
        with lock:
            room = find_room_by_code(room_code)
            if not room:
                raise PublicError("Room not found.")

            player = find_player(player_id, room["id"])
            request_sid = request.sid
            if not player or player.get("socket_sid") != request_sid or not player.get("is_connected"):
                raise PublicError("Your player session is not active. Rejoin the room.")

            if room.get("current_winner_player_id"):
                state = build_room_state(room)
                return {
                    "ok": False,
                    "error": "This round already has a winner.",
                    "winner": state["winner"],
                }

            # This conditional database update is the second guard after the in-process lock.
            # Only the first request that sees a NULL winner can write a winner for the round.
            update_response = (
                db()
                .table("rooms")
                .update(
                    {
                        "current_winner_player_id": player["id"],
                        "updated_at": utc_now(),
                    }
                )
                .eq("id", room["id"])
                .is_("current_winner_player_id", "null")
                .execute()
            )

            if not update_response.data:
                fresh_room = find_room_by_code(room_code)
                state = build_room_state(fresh_room)
                return {
                    "ok": False,
                    "error": "Another player buzzed first.",
                    "winner": state["winner"],
                }

            wins = increment_score(room["id"], player["id"])
            updated_room = update_response.data[0]
            state = build_room_state(updated_room)
            winner = {
                "id": player["id"],
                "name": player["name"],
                "isHost": bool(player.get("is_host")),
                "isConnected": True,
                "wins": wins,
            }

            socketio.emit(
                "winner_selected",
                {
                    "roomCode": room_code,
                    "round": state["round"],
                    "winner": winner,
                },
                room=room_code,
            )
            socketio.emit(
                "scoreboard_update",
                {"roomCode": room_code, "scoreboard": state["scoreboard"]},
                room=room_code,
            )
            return {"ok": True, "winner": winner}
    except Exception as error:
        return public_failure(error, "Could not submit buzz.")


@socketio.on("reset_round")
def handle_reset_round(payload):
    try:
        payload = payload or {}
        room_code = validate_room_code(payload.get("roomCode"))
        host_token = str(payload.get("hostToken") or "")

        lock = get_room_lock(room_code)
        with lock:
            room = find_room_by_code(room_code)
            if not room:
                raise PublicError("Room not found.")
            if not host_token or not secrets.compare_digest(host_token, room["host_token"]):
                raise PublicError("Only the host can reset the round.")

            response = (
                db()
                .table("rooms")
                .update(
                    {
                        "current_winner_player_id": None,
                        "current_round": int(room.get("current_round") or 1) + 1,
                        "updated_at": utc_now(),
                    }
                )
                .eq("id", room["id"])
                .execute()
            )
            updated_room = response.data[0]
            state = build_room_state(updated_room)

            socketio.emit(
                "reset_round",
                {
                    "roomCode": room_code,
                    "round": state["round"],
                    "winner": None,
                    "buzzerLocked": False,
                },
                room=room_code,
            )
            socketio.emit(
                "scoreboard_update",
                {"roomCode": room_code, "scoreboard": state["scoreboard"]},
                room=room_code,
            )
            return {"ok": True, "state": state}
    except Exception as error:
        return public_failure(error, "Could not reset round.")


@socketio.on("disconnect")
def handle_disconnect():
    try:
        request_sid = request.sid
        with sid_registry_guard:
            registry_entry = sid_registry.pop(request_sid, None)
        if not registry_entry:
            return

        room_code = registry_entry["roomCode"]
        player_id = registry_entry["playerId"]
        room = find_room_by_code(room_code)
        if not room:
            return

        # Match the socket id during disconnect so a quick reconnect is not marked offline.
        response = (
            db()
            .table("players")
            .update({"is_connected": False, "last_seen": utc_now()})
            .eq("id", player_id)
            .eq("socket_sid", request_sid)
            .execute()
        )
        if response.data:
            emit_player_and_score_updates(room_code)
    except Exception:
        app.logger.exception("Disconnect cleanup failed.")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_ENV") == "development"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
