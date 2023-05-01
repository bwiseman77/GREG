# GREG Client
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

# Globals

NSERVER = "catalog.cse.nd.edu:9097"
Engine  = chess.engine.SimpleEngine.popen_uci("./stockfish")

# literally most of this is scrap work, i keep confusing myself cuz im so dumb
# main probs are that i think we cant send class stuff through concurrent features, so we need them to be global functions
# how ever this leads to prob of needing to open engine multiple times, but we wanna limit that so only open once per process
# rn, i have two functions, one that loops through current moves and returns the "best move", which is a tuple of move and score, and then another that scores the board. Then there is second function that scors the move. This also does the recusive checks but kinda jank cuz it also calls the first function cuz it needs to loop through all moves but in these calls we only car about score since we are checking the move from the top level call. 

# Functions

def multi_solve(info):
    moves, board, depth = info
    engine = chess.engine.SimpleEngine.popen_uci("./stockfish")

    res = solve(moves, board, depth, engine)

    engine.quit()
    return res

def solve(listOfMoves, board, depth, pretty=False, engine=None):
    '''Loop over a list of moves and return tuple (best move, best score)'''
    bestMove = (None, float("-inf"))

    # get scores of top level moves
    topmoves = []
    for move in listOfMoves:
        score = score_move(move, board, 1) 
        topmoves.append((score, move))

    # only search moves that seem worth it
    top = sorted(topmoves, reverse=True)[:5]
    for score, move in top:
        score = score_move(move, board, depth, pretty)
        if score > bestMove[1]:
            bestMove = (move, score)

    return bestMove

def score_move(move, board, depth, pretty=False, engine=None):
    '''
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
        analyse = Engine.analyse(board, chess.engine.Limit(depth=0))
        score = analyse["score"].pov(turn).score(mate_score=100000)

        # pop from board cuz i think its passed by reference??
        board.pop()
        return score

    # non base case
    else:
        # push whites best move
        opp_move = chess.Move.from_uci(solve([move.uci() for move in board.pseudo_legal_moves if move in board.legal_moves], board, 1, pretty)[0])
        board.push(opp_move)
          
        # for every move in new board, see what is best
        score = solve([move.uci() for move in board.pseudo_legal_moves if move in board.legal_moves], board, depth-1, pretty)

        # pop from board cuz passed by ref???
        board.pop()
        board.pop()
        return score[1]

# Classes 
class ChessWorker:
    def __init__(self, pretty=False, debug=False, name=""):
        global Engine
        self.engine = Engine
        self.pretty = pretty
        self.debug  = debug
        self.name   = name
        self.find_server()

    ############################
    #   Networking Functions   #
    ############################
    def find_server(self):
        '''Locate chess service and connect to it'''
        while True:

            # get json data from nameserver
            conn = http.client.HTTPConnection(NSERVER)
            conn.request("GET", "/query.json")
            js   = json.loads(conn.getresponse().read())

            # set up zmq context
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.DEALER)
            self.monitor = self.socket.get_monitor_socket(zmq.EVENT_CLOSED|zmq.EVENT_HANDSHAKE_SUCCEEDED|zmq.EVENT_DISCONNECTED)

            # look for available server
            for item in js:
                if "type" in item and item["type"] == f"{self.name}chessWorker":
                    if self.debug:
                        print(item)
                    self.port = item["port"]
                    self.host = item["name"]
                    try:
                        if self.connect():
                            return
                    except zmq.ZMQError as exc:
                        print("exc", exc)
                
    def connect(self):      
        '''Connect to a Server using ZMQ'''
        # set up socket
        if self.pretty:
            print(f"connecting to {self.host}:{self.port}")
        self.socket.connect(f"tcp://{self.host}:{self.port}")

        # zmq monitor magic
        try:
            event = zmq.utils.monitor.recv_monitor_message(self.monitor) 
        except zmq.ZMQError as e:
            print(e)
            return False
        # if handshake didnt fail, return true
        if event['event'] == zmq.EVENT_HANDSHAKE_SUCCEEDED:
            print(event["event"])
            return True
        elif event['event'] == zmq.EVENT_CLOSED:
            print(event["event"])
            return False
        #elif event['event'] == zmq.EVENT_CONNECT_DELAYED:
        #    return False
        #elif event['event'] == zmq.EVENT_CONNECT_RETRIED:
        #    return False
        print(event["event"])
        return False
        
    #######################
    #   Chess Functions   #
    #######################
    def spawn(self, moves, board, depth=1):
        for move in moves:
            yield ([move], board, depth)

    def get_jobs(self):
        while True:
            # tell server 'im ready!'
            msg = json.dumps({"type":"WorkerRequest", "status":"Ready"}).encode()
            self.socket.send_multipart([b"", msg])
            c_id, message = self.socket.recv_multipart()
            message       = json.loads(message)

            if self.debug:
                print(message)

            # print board after making move
            moves = message["listOfMoves"]
            b     = message["board"]
            depth = message["depth"]
            board = chess.Board(fen=b)

            # Try multi-core
            #with concurrent.futures.ProcessPoolExecutor(1) as executor:
            #    ans = executor.map(multi_solve, self.spawn([move], board, 2))

            #for a in ans:
            #    print(a)

            s = solve(moves, board, depth, self.pretty)

            # sending the work back to server
            message = json.dumps({"type":"WorkerResult", "move":s[0], "score":s[1], "board":b, "depth":depth}).encode()
            self.socket.send_multipart([c_id, message])

def usage(status):

    print(f"Usage: ./GREGWorker.py [options]")
    print(f"    -n NAME    Add unique name")
    print(f"    -d         Turn on Debugging")
    print(f"    -p         Turn on pretty printing")
    exit(status)

def main():
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
    worker.get_jobs()

    Engine.close()

if __name__ == "__main__":
    main()

# Main Execution
