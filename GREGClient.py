# GREG Client
import zmq
import chess
import sys
import http.client
import json

# Globals

NSERVER = "catalog.cse.nd.edu:9097"

# Classes


class ChessClient:
    def __init__(self):
        self.board = chess.Board()
        self.find_server()

    def find_server(self):
        while True:
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())
            for item in js:
                if "type" in item and item["type"] == "chessClient":
                    print(item)
                    self.port = item["port"]
                    self.host = item["name"]
                    self.connect()
                    return

    def connect(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{self.host}:{self.port}")

    def play_game(self):
        while(True):
            print(self.board.unicode(borders=True,invert_color=True,empty_square=" "))
            if self.board.is_checkmate():
                print(f"game over! {board.outcome().result()}")
                exit(0)
            move = input("Make your move (uci): \n")
            if move == "q":
                print("Ending Game")
                exit(0)
            
            try:
                move = chess.Move.from_uci(move)
            except:
                print("please make a valid move")
                continue

            if move not in self.board.legal_moves:
                print("please make a valid move")
                continue
                
            self.board.push(move)

            # get next move from server
            b = self.board.fen()
            self.socket.send(bytes(b, "utf-8"))

            move = self.socket.recv().decode("utf-8")
            move = chess.Move.from_uci(move)
            self.board.push(move)


# Main Execution
def main():
    print("Welcome to the GREG chess application! (q to quit)")        
    client = ChessClient()       

    print("play game")
    client.play_game()


if __name__ == "__main__":
    main()
