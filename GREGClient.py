# GREG Client
import zmq
import zmq.utils.monitor
import chess
import sys
import http.client
import json
import time
import signal
import os

# Globals

NSERVER      = "catalog.cse.nd.edu:9097"
UPDATE_DELAY = 60

# Classes
class ChessClient:
    HEARTBEAT_INTERVAL = 30000
    HEARTBEAT_INTERVAL_S = 30

    def __init__(self, depth=1):
        self.board = chess.Board()
        self.context = zmq.Context()
        self.find_server()
        self.depth = depth

        signal.setitimer(signal.ITIMER_REAL, 30, self.HEARTBEAT_INTERVAL_S)
        signal.signal(signal.SIGALRM, self.send_heartbeat)

    ############################
    #   Networking functions   #
    ############################
    def find_server(self):
        '''Locate chess server from name server'''
        while True:
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())
            
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.DEALER)
            self.monitor = self.socket.get_monitor_socket(zmq.EVENT_CLOSED|zmq.EVENT_HANDSHAKE_SUCCEEDED|zmq.EVENT_DISCONNECTED)

            # look for available server
            for item in js:
                if "type" in item and item["type"] == "MiachessClient" and int(item["lastheardfrom"]) + UPDATE_DELAY > time.time():
                    print(item)
                    self.port = item["port"]
                    self.host = item["name"]

                    try:
                        if self.connect():
                            return
                    except zmq.ZMQError as exc:
                        print(exc)
                    
    def connect(self):
        '''Connect to chess server, and checks to make handshake was successful'''
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        
        try:
            event = zmq.utils.monitor.recv_monitor_message(self.monitor)
        except zmq.ZMQError as e:
            print(e)
            return False
        if event['event'] == zmq.EVENT_HANDSHAKE_SUCCEEDED:
            return True
        elif event['event'] == zmq.EVENT_CLOSED:
            return False
        return False


    def send_heartbeat(self, signum, frame):
        msg = json.dumps({"type": "<3"}).encode()
        self.socket.send(msg)
        print("sent <3")

            
    #######################
    #   Chess Functions   #
    #######################
    def play_game(self):
        '''Main game play function'''
        while(True):
            # print board
            print(self.board.unicode(borders=True,invert_color=True,empty_square=" "))
            
            # check for end of game
            if self.board.is_checkmate():
                print(f"game over! {self.board.outcome().result()}")
                exit(0)

            # get next move from user
            move = input("Make your move (uci): \n")

            # q to quit game
            if move == "q":
                print("Ending Game")
                exit(0)
            
            # try convert move, if invalid ask again (needs to be uci)
            try:
                move = chess.Move.from_uci(move)
            except:
                print("please make a valid move")
                continue

            # if not a legal move, retry
            if move not in self.board.legal_moves:
                print("please make a valid move")
                continue
                
            # add the move
            self.board.push(move)

            # print board for user
            os.system('clear')
            print(self.board.unicode(borders=True,invert_color=True,empty_square=" "))

            # get next move from server
            b = self.board.fen()
            
            # send the message
            self.socket.send(bytes(json.dumps({"board":b, "depth":self.depth}), "utf-8"))

            # recv move
            id_, msg = self.socket.recv_multipart()
            msg      = json.loads(msg)
            print(msg)
            
            
            # convert move and push to board
            move = msg["move"]
            move = chess.Move.from_uci(move)
            self.board.push(move)
            os.system('clear')

def usage(status):

    print(f"Usage: ./GREGClient.py [options]")
    print(f"    -d DEPTH    Depth of searches (depth = 1)")
    print(f"    -h          help")
    return status

# Main Execution
def main():
    depth = 1
    if len(sys.argv) == 3:
        depth = int(sys.argv[2]) 

    if len(sys.argv) == 2:
        usage(0)
    
    print("Welcome to the GREG chess application! (q to quit)")      
    client = ChessClient(depth)       
    client.play_game()


if __name__ == "__main__":
    main()
