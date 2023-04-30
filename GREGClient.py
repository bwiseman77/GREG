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
    def __init__(self, depth=1, isBlack=True, name="", silent=False):
        self.board   = chess.Board()
        self.context = zmq.Context()
        self.isBlack = isBlack
        self.depth   = depth
        self.name    = name
        self.silent  = silent
        self.find_server()

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
                if "type" in item and item["type"] == f"{self.name}chessClient" and int(item["lastheardfrom"]) + UPDATE_DELAY > time.time():
                    if not self.silent:
                        print(item)
                    self.port = item["port"]
                    self.host = item["name"]

                    try:
                        if self.connect():
                            return
                    except zmq.ZMQError as exc:
                        if not self.silent:
                            print(exc)
                    
    def connect(self):
        '''Connect to chess server, and checks to make handshake was successful'''
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        
        try:
            event = zmq.utils.monitor.recv_monitor_message(self.monitor)
        except zmq.ZMQError as e:
            if not self.silent:
                print(e)
            return False
        if event['event'] == zmq.EVENT_HANDSHAKE_SUCCEEDED:
            return True
        elif event['event'] == zmq.EVENT_CLOSED:
            return False
        elif event['event'] == zmq.EVENT_CONNECTION_DELAYED:
            return False
        elif event['event'] == zmq.EVENT_CONNECTION_RETRIED:
            return False
        return False

            
    #######################
    #   Chess Functions   #
    #######################
    def play_game(self):
        '''Main game play function'''


        if self.isBlack:
            # print empty board
            if not self.silent:
                print(self.board.unicode(borders=True,invert_color=True,empty_square=" ", orientation=not self.isBlack))
            
            # ask for move
            b = self.board.fen()
            self.socket.send(bytes(json.dumps({"board":b, "depth":self.depth}), "utf-8"))
            
            # recv move
            id_, msg = self.socket.recv_multipart()
            msg      = json.loads(msg)
            
            # convert move and push to board
            move = msg["move"]
            print("CPU move: ", move)
            move = chess.Move.from_uci(move)
            self.board.push(move)
            
        while(True):
            # print board
            if not self.silent:
                print(self.board.unicode(borders=True,invert_color=True,empty_square=" ", orientation=not self.isBlack))
            
            # check for end of game
            if self.board.is_checkmate() or self.board.is_stalemate() or self.board.is_insufficient_material():
                print(f"game over! {self.board.outcome().result()}")
                exit(0)

            # get next move from user
            if self.silent:
                move = input() #sys.stdin.readline().decode()
                
            else:
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
            if not self.silent:
                os.system('clear')
                print(self.board.unicode(borders=True,invert_color=True,empty_square=" ", orientation= not self.isBlack))

            
            
            # send the message
            b = self.board.fen()
            self.socket.send(bytes(json.dumps({"board":b, "depth":self.depth}), "utf-8"))

            # recv move
            id_, msg = self.socket.recv_multipart()
            msg      = json.loads(msg)
            
            
            # convert move and push to board
            move = msg["move"]
            move = chess.Move.from_uci(move)
            self.board.push(move)
            if not self.silent:
                os.system('clear')
            print("CPU move: ", move.uci()) 

def usage(status):

    print(f"Usage: ./GREGClient.py [options]")
    print(f"    -d DEPTH    Depth of searches (depth = 1)")
    print(f"    -n NAME     Add unique name")
    print(f"    -b          Play as black instead of white")
    print(f"    -h          help")
    print(f"    -s          silent mode")

    exit(status)

# Main Execution
def main():
    # options
    depth   = 1
    isBlack = False
    silent  = False
    name    = ""
    argind  = 1
    
    # parse command args
    while argind < len(sys.argv):
        arg = sys.argv[argind]
        if arg == "-d":
            argind += 1
            depth = int(sys.argv[argind])
        elif arg == "-b":
            isBlack = True
        elif arg == "-n":
            argind += 1
            name = sys.argv[argind]
        elif arg == "-s":
            silent = True
        elif arg == "-h":
            usage(0)
        else:
            usage(1)
        argind += 1
    
    # play game
    if not silent:
        print("Welcome to the GREG chess application! (q to quit)")      
    client = ChessClient(depth, isBlack, name, silent)
    client.play_game()


if __name__ == "__main__":
    main()
