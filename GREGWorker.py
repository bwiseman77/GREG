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
        self.port = 5556
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
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        print("connected ", self.socket)
        
    def find_move(self):
        while True:

            # tell server 'im ready!'
            self.socket.send_multipart([b"", b"ready"])
            c_id, board, message = self.socket.recv_multipart()
            
            # print board after making move
            move = message.decode("utf-8")
            b = board.decode()
            board = chess.Board(fen=b)
            board.push(chess.Move.from_uci(move))
            print(board)

            # checking legal moves and just sending a score, move, back
            max_score = 0
            legal_move = None
            for move in board.pseudo_legal_moves:
                if move not in board.legal_moves:
                    continue
                legal_move = move
                print(move)
                pass

            score = 5 # random number for testing

            # sending the work back to server
            message = str(score) + "," + str(legal_move)
            self.socket.send_multipart([c_id, message.encode("utf-8")])

def main():
    worker = ChessWorker()
    worker.find_move()

if __name__ == "__main__":
    main()

# Main Execution
