# GREG Client
import zmq
import chess
import time
import stockfish
import sys
import http.client
import json

# Globals

NSERVER = "catalog.cse.nd.edu:9097"

# Classes

class ChessWorker:
    def __init__(self):
        self.port = 5557
        self.host = '127.0.0.1'
        #self.find_server()
        self.connect()

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
                    try:
                        self.connect()
                        #self.socket.send_string(".", flags=zmq.NOBLOCK)
                        #time.sleep(.1)

                    except zmq.ZMQError as exc:
                        print("exc", exc)
                
    def connect(self):
        print("connect")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        print("connected ", self.socket)

    def find_move(self):
        while True:
            print('waiting for move')
            message = self.socket.recv()
            print(f"received message: {message}")
            self.socket.send(message)

            b = message.decode("utf-8")
            board = chess.Board(fen=b)
            print(board)

            #while True:
            #    move = input("Make your move (uci): \n")
            #    if chess.Move.from_uci(move) in board.legal_moves:
            #        break
            max_score = 0
            for move in board.legal_moves:
                print(move)
                pass


            
            self.socket.send(bytes(move, "utf-8"))

def main():
    worker = ChessWorker()
    worker.find_move()

if __name__ == "__main__":
    main()

# Main Execution
