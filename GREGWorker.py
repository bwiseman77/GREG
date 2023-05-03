# GREG Worker
import zmq
import zmq.utils.monitor
import chess
import chess.engine
import sys
import http.client
import json
import concurrent.futures
import time
import zmq.utils.monitor
import signal

# Globals
NSERVER = "catalog.cse.nd.edu:9097"
Engine  = chess.engine.SimpleEngine.popen_uci("./bin/stockfish")

# Functions
def usage(status):
    '''
    param:  status
    return: None
    Usage function that exits with STATUS
    '''
    print(f"Usage: ./GREGWorker.py [options]")
    print(f"    -n NAME    Add unique name")
    print(f"    -d         Turn on Debugging")
    print(f"    -p         Turn on pretty printing")
    exit(status)


# Classes 
class ChessWorker:
    HEARTBEAT_INTERVAL = 5000
    HEARTBEAT_INTERVAL_S = 5

    #########################
    #    Class Functions    #
    #########################
    def __init__(self, pretty=False, debug=False, name=''):
        global Engine
        self.engine = Engine
        self.pretty = pretty
        self.debug  = debug
        self.name   = name
        self.connected = False
        self.find_server()

        # <3
        signal.setitimer(signal.ITIMER_REAL, self.HEARTBEAT_INTERVAL_S, self.HEARTBEAT_INTERVAL_S)
        signal.signal(signal.SIGALRM, self.send_heartbeat) 
        
        self.heartbeat_at = 0


    def printg(self, msg, alwaysPrint=False):
        '''
        param:  msg string:         message to print
        param:  alwaysPrint bool:   if message should always be printed
        return: None
        Wrapper for print statements for debugging
        '''
        if alwaysPrint:
            print(msg)
        else:
            if self.debug:
                print(msg)

    
    ############################
    #   Networking Functions   #
    ############################
    def find_server(self):
        '''
        param:  None
        return: None
        Locate chess service and connect to it
        '''
        while True:

            # get json data from nameserver
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())

            # set up zmq context
            self.context = zmq.Context()
            
            # look for available server
            for item in js:
                if "type" in item and item["type"] == f"{self.name}chessWorker":
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
        # set up socket        
        self.socket.connect(f"tcp://{self.host}:{self.port}")

        # zmq monitor magic
        try:
            event = zmq.utils.monitor.recv_monitor_message(self.monitor) 
        except zmq.ZMQError as e:
            self.printg(e)
            return False
        # if handshake didnt fail, return true
        if event['event'] == zmq.EVENT_HANDSHAKE_SUCCEEDED:
            return True
        elif event['event'] == zmq.EVENT_DISCONNECTED or event['event'] == zmq.EVENT_CLOSED:
            self.monitor.close()
            self.socket.close()
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
            self.socket.send_multipart([b"", msg])
            self.printg("sent <3")
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
    def score_move(self, move, board, depth, pretty=False):
        '''
            param:  move string:     move to look at
            param:  board Board:     current chess.py board
            param:  pretty bool:     pretty printing
            return: score int:       score of a move
            Scores a board. 
            Base case is depth == 1, which just returns the score of current board
            If depth > 1, then find "best" move for white, and then call solve on this list of moves, returning the score of the best one
            
        '''
        global Engine

        # push blacks move
        turn = board.turn
        board.push(chess.Move.from_uci(move))

        # print to look fancy
        if pretty:
            print(board.unicode(borders=True, invert_color=True,empty_square=" ", orientation = turn))

        # base case
        if depth == 1:

            # get score of board
            try:
                analyse = Engine.analyse(board, chess.engine.Limit(depth=0))
            except:
                return -10000000

            score = analyse["score"].pov(turn).score(mate_score=100000)

            # pop from board cuz i think its passed by reference
            board.pop()
            return score

        # non base case
        else:
            # push whites best move
            opp_moves = [move.uci() for move in board.pseudo_legal_moves if move in board.legal_moves]
            if opp_moves == []:
                board.pop()
                return 10000000    

            opp_move = chess.Move.from_uci(self.solve(opp_moves, board, 1, pretty)[0])

            board.push(opp_move)
              
            # for every move in new board, see what is best
            best_moves = [move.uci() for move in board.pseudo_legal_moves if move in board.legal_moves]
            if best_moves == []:
                board.pop()
                board.pop()
                return -10000000

            score = self.solve(best_moves, board, depth-1, pretty)
            
            # pop from board cuz passed by ref
            board.pop()
            board.pop()
            return score[1]


    def solve(self, listOfMoves, board, depth, pretty=False):
        '''
        param:  listOfMoves list:   List of moves to compute
        param:  board Board:        current chess.py Board
        param:  depth int:          current depth
        param:  pretty bool:        pretty printing
        return  turple of (score, move)
        Loop over a list of moves and return tuple (best move, best score)
        '''
        bestMove = (None, float("-inf"))

        # get scores of top level moves
        topmoves = []
        for move in listOfMoves:
            score = self.score_move(move, board, 1) 
            topmoves.append((score, move))

        # only search moves that seem worth it
        top = sorted(topmoves, reverse=True)[:5]
        for score, move in top:
            score = self.score_move(move, board, depth, pretty)
            if score > bestMove[1]:
                bestMove = (move, score)
        if bestMove[0] == None:
            return (None, -1000000)
        return bestMove


    def get_jobs(self):
        '''
        param:  None
        return: None
        Main loop of worker, commincates with server to get jobs and returns them
        '''

        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        poller.register(self.monitor, zmq.POLLIN)

        while True:
            # tell server 'im ready!'
            msg = json.dumps({"type":"WorkerRequest", "status":"Ready"}).encode()
            if self.debug:
                print("sent readyyy")

            self.socket.send_multipart([b'', msg])
            self.update_expiry()

            socks = dict(poller.poll())
            
            # monitor has message
            if self.monitor in socks and socks[self.monitor] == zmq.POLLIN:
                event = zmq.utils.monitor.recv_monitor_message(self.monitor) 
                # on a disconnect, find server again and get jobs again
                if event['event'] == zmq.EVENT_CLOSED:
                    self.connected = False
                    self.monitor.close()
                    self.socket.close()
                    self.context.destroy()
                    self.find_server()
                    return

            # if socket has message with work
            if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                client_id, message = self.socket.recv_multipart()
                message       = json.loads(message)

                if self.debug:
                    print(message)

                # print board after making move
                moves = message["listOfMoves"]
                b     = message["board"]
                depth = message["depth"]
                board = chess.Board(fen=b)

                s = self.solve(moves, board, depth, self.pretty)

                # sending the work back to server
                message = json.dumps({"type":"WorkerResult", "move":s[0], "score":s[1], "board":b, "depth":depth}).encode()
                self.socket.send_multipart([client_id, message])


# Main Execution
def main():
    '''
    Main execution
    '''
    # options
    pretty = False
    debug  = False
    name   = ""
    argind = 1

    # parse args
    while argind < len(sys.argv):
        arg = sys.argv[argind]
        if arg == "-p":
            pretty = True
        elif arg == "-d":
            debug == True
        elif arg == "-n":
            argind += 1
            name = sys.argv[argind]
        elif arg == "-h":
            usage(0)
        else:
            usage(1)

        argind += 1

    # start doing work
    worker = ChessWorker(pretty, debug, name)
    while True:
        worker.get_jobs()
    
    Engine.close()

if __name__ == "__main__":
    main()
