# GREG Client
import zmq
import chess
import chess.engine
import sys
import http.client
import json
import time

# Globals

NSERVER = "catalog.cse.nd.edu:9097"

# Classes

class ChessWorker:
    def __init__(self):
        self.find_server()
        self.engine = chess.engine.SimpleEngine.popen_uci("./stockfish")

    def find_server(self):
        while True:
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())
            for item in js:
                if "type" in item and item["type"] == "chessWorkerBrett":
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

    def find_move(self, curr_move, board, depth=1):
        if depth == 1:
            best_move = (None,chess.engine.Mate(0))
            print(board.pseudo_legal_moves.count())
            turn = board.turn
            for move in board.pseudo_legal_moves:
                #print(move)
                if move not in board.legal_moves:
                    continue

                board.push(move)
                score = self.engine.analyse(board, chess.engine.Limit(depth=0))["score"].pov(turn)
                if best_move[1] < score:
                    best_move = (move, score)
                board.pop()
    
            return best_move

        else:
            best_move = (None,chess.engine.Mate(0))
            turn = board.turn
            for move in board.pseudo_legal_moves:
                if move not in board.legal_moves:
                    continue

                board.push(move)
               
                # need to decide how to deal with mates - possibly insta good or insta bad
                try:
                    board.push(self.find_move(0, board.copy())[0])
                    print(board)
                    board.push(self.find_move(0, board.copy(), depth-1)[0])
                except:
                    continue
                score = self.engine.analyse(board, chess.engine.Limit(depth=0))["score"].pov(turn)
                if best_move[1] < score:
                    best_move = (move, score)
                board.pop()
                board.pop()
                board.pop()

            return best_move



                

    def get_jobs(self):
        while True:
            message = self.socket.recv()
            print(f"{message}")

            b = message.decode("utf-8")
            board = chess.Board(fen=b)
            turn  = board.turn
            move = self.find_move(0, board.copy(), 3)[0]
            
            self.socket.send(bytes(chess.Move.uci(move), "utf-8"))

def main():
    worker = ChessWorker()
    worker.get_jobs()

if __name__ == "__main__":
    main()

# Main Execution
