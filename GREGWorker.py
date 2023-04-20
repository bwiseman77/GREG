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
        self.find_server()

    
    def find_server(self):
        while True:
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())

            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.DEALER)
            self.monitor = self.socket.get_monitor_socket()

            for item in js:
                if "type" in item and item["type"] == "chessWorker":
                    print(item)
                    self.port = item["port"]
                    self.host = item["name"]
                    try:
                        if self.connect():
                            return
                    except zmq.ZMQError as exc:
                        print("exc", exc)
                
    def connect(self):        
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        while True:
            try:
                event = self.monitor.recv_multipart()
            except zmq.ZMQError as e:
                print(e)
                return False
            event_type = event[0]
            event_addr = event[1]
            if int.from_bytes(event_type, byteorder='little') == int(zmq.EVENT_HANDSHAKE_SUCCEEDED):
                return True
        return False
        
    
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
