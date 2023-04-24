# GREG Client
import zmq
import chess
import chess.engine
import sys
import http.client
import json
import concurrent.futures
import time

# Globals

NSERVER = "catalog.cse.nd.edu:9097"
Engine  = None

# Functions

# literally most of this is scrap work, i keep confusing myself cuz im so dumb
# main probs are that i think we cant send class stuff through concurrent features, so we need them to be global functions
# how ever this leads to prob of needing to open engine multiple times, but we wanna limit that so only open once per process
# rn, i have two functions, one that loops through current moves and returns the "best move", which is a tuple of move and score, and then another that scores the board. Then there is second function that scors the move. This also does the recusive checks but kinda jank cuz it also calls the first function cuz it needs to loop through all moves but in these calls we only car about score since we are checking the move from the top level call. 

def solve(listOfMoves, board, depth):
    '''Loop over a list of moves and return tuple (best move, best score)'''
    bestMove = (None, float("-inf"))
    for move in listOfMoves:
        score = score_move(move, board, depth)
        print(board)
        if score > bestMove[1]:
            bestMove = (move, score)

    return bestMove

def score_move(move, board, depth):
    '''
        Scores a board. 
        Base case is depth == 1, which just returns the score of current board
        If Depth > 1, then find "best" move for white, and then call solve on this list of moves, returning the score of the best one
        
    '''
    global Engine
    engine = Engine
    #engine = chess.engine.SimpleEngine.popen_uci("./stockfish")
    turn = board.turn
    if depth == 1:
        board.push(chess.Move.from_uci(move))
        score = engine.analyse(board, chess.engine.Limit(depth=0))
        #print(score)
        score = score["score"].pov(turn)
        #print(score)
        score = score.score(mate_score=100000)
        #print(board,score)
        board.pop()
        #engine.quit()
        return score
    else:
        # push blacks move
        board.push(chess.Move.from_uci(move))

        # push whites best move
        board.push(chess.Move.from_uci(solve([move.uci() for move in board.pseudo_legal_moves if move in board.legal_moves], board, 1)[0]))
        
        # for every move in new board, see what is best
        score = solve([move.uci() for move in board.pseudo_legal_moves if move in board.legal_moves], board, depth-1)[1]
        board.pop()
        board.pop()
        #engine.quit()
        return score
# Classes 

class ChessWorker:
    def __init__(self):
        self.find_server()
        self.engine = chess.engine.SimpleEngine.popen_uci("./stockfish")
        global Engine
        Engine = self.engine

    
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
            self.monitor = self.socket.get_monitor_socket()

            # look for available server
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
        '''Connect to a Server using ZMQ'''
        # set up socket
        self.socket.connect(f"tcp://{self.host}:{self.port}")

        # zmq monitor magic
        while True:
            try:
                event = self.monitor.recv_multipart()
            except zmq.ZMQError as e:
                print(e)
                return False
            event_type = event[0]
            event_addr = event[1]

            # if handshake didnt fail, return true
            if int.from_bytes(event_type, byteorder='little') == int(zmq.EVENT_HANDSHAKE_SUCCEEDED):
                return True

        return False
        
                      
    def get_jobs(self):
        while True:
            # tell server 'im ready!'
            self.socket.send_multipart([b"", b"ready"])
            c_id, board, message = self.socket.recv_multipart()
            
            # print board after making move
            move = message.decode("utf-8")
            b = board.decode()
            board = chess.Board(fen=b)

            s = solve([move], board, 2)

            # sending the work back to server
            message = str(s[1]) + "," + s[0]
            print(message)
            self.socket.send_multipart([c_id, message.encode("utf-8")])


def main():
    worker = ChessWorker()
    worker.get_jobs()

if __name__ == "__main__":
    main()

# Main Execution
