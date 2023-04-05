# GREG Client
import zmq
import chess
import sys
import http.client
import json

# Globals

NSERVER = "catalog.cse.nd.edu:9097"

# Classes

class ChessWorker:
    def __init__(self):
        self.find_server()

    def find_server(self):
        while True:
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())
            for item in js:
                if "type" in item and item["type"] == "chessWorker":
                    print(item)
                    self.port = item["port"]
                    self.host = item["name"]
                    self.connect()
                    return

    def connect(self):
        print("connect")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.connect(f"tcp://{self.host}:{self.port}")

    def find_move(self):
        while True:
            message = self.socket.recv()
            print(f"{message}")

            b = message.decode("utf-8")
            board = chess.Board(fen=b)
            print(board)

            while True:
                move = input("Make your move (uci): \n")
                if chess.Move.from_uci(move) in board.legal_moves:
                    break

            
            self.socket.send(bytes(move, "utf-8"))

def main():
    worker = ChessWorker()
    worker.find_move()

if __name__ == "__main__":
    main()

# Main Execution
