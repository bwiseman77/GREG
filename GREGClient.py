# GREG Client
import zmq
import chess
import sys
import http.client
import json
import time
import signal

# Globals

NSERVER      = "catalog.cse.nd.edu:9097"
UPDATE_DELAY = 60

# Classes
class ChessClient:
    def __init__(self):
        self.board = chess.Board()
        self.context = zmq.Context()
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
                if "type" in item and item["type"] == "chessClient" and int(item["lastheardfrom"]) + UPDATE_DELAY > time.time():
                    self.port = item["port"]
                    self.host = item["name"]

                    try:
                        if self.connect():
                            return
                    except zmq.ZMQError as exc:
                        print(exc)
                    

    def connect(self):
        # start old
        #self.socket = self.context.socket(zmq.REQ)
        #return self.socket.connect(f"tcp://{self.host}:{self.port}")
        # end old

        self.socket.connect(f"tcp://{self.host}:{self.port}")
        while True:
            try:
                event = self.monitor.recv_multipart()
            except zmq.ZMQError as e:
                print(e)
                return False

            event_type = event[0]
            event_addr = event[1]
            #print(int.from_bytes(event_type, byteorder='little') == int(zmq.EVENT_HANDSHAKE_SUCCEEDED))
            if int.from_bytes(event_type, byteorder='little') == int(zmq.EVENT_HANDSHAKE_SUCCEEDED):
                return True
            print("nope", self.port)
        return False
            


    def play_game(self):
        while(True):
            print(self.board.unicode(borders=True,invert_color=True,empty_square=" "))
            if self.board.is_checkmate():
                print(f"game over! {self.board.outcome().result()}")
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
            
            # start old
            #self.socket.send(bytes(b, "utf-8"))  
            #move = self.socket.recv().decode("utf-8") 
            # end old

            self.socket.send(bytes(b, "utf-8"))
            #self.socket.send_multipart([b"client1", bytes(b, "utf-8")])
            print("ya sent a message")

            id_, move = self.socket.recv_multipart()

            move = move.decode()
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
