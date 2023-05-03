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

# Functions
def usage(status):

    print(f"Usage: ./GREGClient.py [options]")
    print(f"    -d DEPTH    Depth of searches (depth = 1)")
    print(f"    -n NAME     Add unique name")
    print(f"    -b          Play as black instead of white")
    print(f"    -h          help")
    print(f"    -s          silent mode")

    exit(status)

# Classes
class ChessClient:
    HEARTBEAT_INTERVAL = 5000
    HEARTBEAT_INTERVAL_S = 5

    #########################
    #    Class Functions    #
    #########################
    def __init__(self, depth=1, isBlack=True, name="", silent=False):
        self.board   = chess.Board()
        self.context = zmq.Context()
        self.isBlack = isBlack
        self.depth   = depth
        self.name    = name
        self.silent  = silent
        self.connected = False
        self.heartbeat_at = 0
        self.find_server()

        signal.setitimer(signal.ITIMER_REAL, self.HEARTBEAT_INTERVAL_S, self.HEARTBEAT_INTERVAL_S)
        signal.signal(signal.SIGALRM, self.send_heartbeat)
    
    def printg(self, msg, alwaysPrint=False):
        '''
        param:  msg string:         message to print
        param:  alwaysPrint bool:   if message should always print
        return: None
        Wrapper for print statements for debugging
        '''
        if alwaysPrint:
            print(msg)
        else:
            if not self.silent:
                print(msg)


    ############################
    #   Networking functions   #
    ############################
    def find_server(self):
        '''
        param:  None
        return: None
        Locate chess service and connect to it
        '''
        while True:
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())
            
            self.context = zmq.Context()
           

            # look for available server
            for item in js:
                if "type" in item and item["type"] == f"{self.name}chessClient" and int(item["lastheardfrom"]) + UPDATE_DELAY > time.time():
                    self.printg(item)
                    self.port = item["port"]
                    self.host = item["name"]

                    try:
                        self.socket = self.context.socket(zmq.DEALER)
                        self.monitor = self.socket.get_monitor_socket(zmq.EVENT_CLOSED|zmq.EVENT_HANDSHAKE_SUCCEEDED|zmq.EVENT_DISCONNECTED)
                        if self.connect():
                            self.connected = True
                            return
                        else:
                            self.monitor.close()
                            self.socket.close()

                    except zmq.ZMQError as exc:
                        self.printg(exc)
                    
    def connect(self):
        '''
        param:  None
        return: True if successful and False otherwise
        Connect to a Server using ZMQ
        '''
        self.socket.connect(f"tcp://{self.host}:{self.port}")
        
        try:
            event = zmq.utils.monitor.recv_monitor_message(self.monitor)
        except zmq.ZMQError as e:
            self.printg(e)
            return False
        if event['event'] == zmq.EVENT_HANDSHAKE_SUCCEEDED:
            return True
        elif event['event'] == zmq.EVENT_CLOSED:
            return False
        return False


    def send_heartbeat(self, signum, frame):
        '''
        param:  signum Signal
        param:  frame Stackframe
        return: None
        Sends heartbeat to server
        '''
        if self.connected and self.heartbeat_at < time.time():
            msg = json.dumps({"type": "<3"}).encode()
            self.socket.send(msg)
            self.update_expiry()

    def update_expiry(self):
        '''
        param:  None
        return: None
        Updates heartbeat time
        '''
        self.heartbeat_at = time.time() + 1e-3*self.HEARTBEAT_INTERVAL

            
    #######################
    #   Chess Functions   #
    #######################
    def play_game(self):
        '''
        param:  None
        return: None
        Main game play function
        '''
        move = ""

        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        poller.register(self.monitor, zmq.POLLIN)

        if self.isBlack:
            # print empty board
            self.printg(self.board.unicode(borders=True,invert_color=True,empty_square=" ", orientation=not self.isBlack))
            
            # ask for move
            b = self.board.fen()
            self.socket.send(bytes(json.dumps({"board":b, "depth":self.depth}), "utf-8"))
            self.update_expiry()
            
            # recv move
            id_, msg = self.socket.recv_multipart()
            msg      = json.loads(msg)
            
            # convert move and push to board
            move = msg["move"]
            move = chess.Move.from_uci(move)
            self.board.push(move)
            
        new_move = True
        while(True):
            if new_move:
                try_send = True

                # check for end of game
                if self.board.is_checkmate() or self.board.is_stalemate() or self.board.is_insufficient_material() or self.board.is_seventyfive_moves(): #` or self.board.is_fivefold_repetition():
                    print(f"game over! {self.board.outcome().result()}", flush=True)
                    exit(0)
                
                if move != "":
                    self.printg(f"CPU move: {move}", True)

                # print board
                self.printg(self.board.unicode(borders=True,invert_color=True,empty_square=" ", orientation=not self.isBlack))
                
                # get next move from user                    
                move = input("Make your move (uci): \n")

                # q to quit game
                if move == "q":
                    self.printg("Ending Game", True)
                    exit(0)
                
                # try convert move, if invalid ask again (needs to be uci)
                try:
                    move = chess.Move.from_uci(move)
                except:
                    self.printf("please make a valid move", True)
                    continue

                # if not a legal move, retry
                if move not in self.board.legal_moves:
                    self.printg("please make a valid move", True)
                    continue
                    
                # add the move
                self.board.push(move)

                # print board for user
                if not self.silent:
                    os.system('clear')
                    print(self.board.unicode(borders=True,invert_color=True,empty_square=" ", orientation= not self.isBlack))

            if try_send:

                # send the message
                b = self.board.fen()
                self.socket.send(bytes(json.dumps({"board":b, "depth":self.depth}), "utf-8"))
                self.update_expiry()

            socks = dict(poller.poll())

            if self.monitor in socks and socks[self.monitor] == zmq.POLLIN:
                new_move = False
                
                event = zmq.utils.monitor.recv_monitor_message(self.monitor)
                if event['event'] == zmq.EVENT_CLOSED or event['event'] == zmq.EVENT_DISCONNECTED:
                    try_send = True
                    self.connected = False
                    self.monitor.close()
                    self.socket.close()
                    self.find_server()
                    poller = zmq.Poller()
                    poller.register(self.monitor, zmq.POLLIN)
                    poller.register(self.socket, zmq.POLLIN)
                    continue
                else:
                    try_send = False

            # recv move
            if self.socket in socks and socks[self.socket] == zmq.POLLIN:

                id_, msg = self.socket.recv_multipart()
                msg      = json.loads(msg)
                
                
                # convert move and push to board
                move = msg["move"]
                move = chess.Move.from_uci(move)
                self.board.push(move)
                if not self.silent:
                    os.system('clear')
                new_move = True
                 

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
