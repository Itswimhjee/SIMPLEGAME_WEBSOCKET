from flask import Flask, render_template, redirect, url_for, request
from flask_socketio import SocketIO, emit, join_room
import uuid
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

rooms = {}  # semua room aktif

@app.route("/")
def index():
    return render_template("index.html", rooms=rooms.keys())

@app.route("/create-circle-room")
def create_circle_room():
    room_id = str(uuid.uuid4())[:6]
    rooms[room_id] = {
        "players": [],  # list nama player
        "board": [""]*9,
        "turn": None,
        "vs_computer": False
    }
    return redirect(url_for("circle_room", room_id=room_id))

@app.route("/circle-room/<room_id>")
def circle_room(room_id):
    if room_id not in rooms:
        return "Room tidak ada"
    return render_template("game.html", room_id=room_id)

# SocketIO events
@socketio.on("join_room_game")
def join_room_game(data):
    room_id = data["room_id"]
    name = data.get("name", "Player")
    vs_computer = data.get("vs_computer", False)

    if room_id not in rooms:
        emit("error", {"msg": "Room tidak ada"})
        return

    room = rooms[room_id]

    # Batasi max 2 player
    if len(room["players"]) >= 2:
        emit("room_full")
        return

    join_room(room_id)
    room["players"].append(name)
    room["vs_computer"] = vs_computer

    # Tentukan giliran pertama
    if not room["turn"]:
        room["turn"] = room["players"][0]

    emit("update_state", {
        "board": room["board"],
        "turn": room["turn"],
        "players": room["players"],
        "vs_computer": room["vs_computer"]
    }, room=room_id)

@socketio.on("make_move")
def make_move(data):
    room_id = data["room_id"]
    index = data["index"]
    player_name = data.get("name", "Player")

    if room_id not in rooms:
        return

    room = rooms[room_id]
    board = room["board"]

    # validasi giliran dan cell kosong
    if board[index] != "" or room["turn"] != player_name:
        return

    board[index] = "X" if room["turn"] == room["players"][0] else "O"

    winner = check_winner(board)
    if winner or "" not in board:
        emit("game_over", {"winner": winner}, room=room_id)
        return

    # ganti giliran
    if room["vs_computer"] and room["turn"] == room["players"][0]:
        room["turn"] = "Computer"
        # AI move
        ai_index = random.choice([i for i, v in enumerate(board) if v == ""])
        board[ai_index] = "O"
        winner = check_winner(board)
        room["turn"] = room["players"][0]
    else:
        room["turn"] = room["players"][0] if room["turn"] == room["players"][-1] else room["players"][-1]

    emit("update_state", {
        "board": board,
        "turn": room["turn"],
        "players": room["players"],
        "vs_computer": room["vs_computer"]
    }, room=room_id)

def check_winner(board):
    lines = [
        [0,1,2],[3,4,5],[6,7,8],  # rows
        [0,3,6],[1,4,7],[2,5,8],  # cols
        [0,4,8],[2,4,6]           # diagonals
    ]
    for a,b,c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None

@socketio.on("leave_room")
def leave_room_event(data):
    room_id = data["room_id"]
    name = data.get("name")
    if room_id in rooms:
        room = rooms[room_id]
        if name in room["players"]:
            room["players"].remove(name)
        if len(room["players"]) == 0:
            del rooms[room_id]
        else:
            # reset board jika pemain keluar
            room["board"] = [""]*9
            room["turn"] = room["players"][0]
            emit("update_state", {
                "board": room["board"],
                "turn": room["turn"],
                "players": room["players"],
                "vs_computer": room["vs_computer"]
            }, room=room_id)

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=8080, debug=True)
