#Greg Server

import time
import zmq
import chess
import signal
import sys
import json
import socket
from threading import Thread

# from the stack overflow thingy
import random
from multiprocessing import Pool, Process

# Globals
NSERVER = "catalog.cse.nd.edu"
NPORT   = 9097

# Classes 
class ChessServer:
    def __init__(self, w_port=5556, c_port=5558):
        self.w_port = w_port
        self.c_port = c_port

        self.context = zmq.Context()
        self.router = self.context.socket(zmq.ROUTER)
        self.client = self.context.socket(zmq.ROUTER)
        
        self.router.bind(f"tcp://*:{self.w_port}")
        self.client.bind(f"tcp://*:{self.c_port}")

        # set up name server pinging
        signal.setitimer(signal.ITIMER_REAL, 1, 60)
        signal.signal(signal.SIGALRM, self.update_nameserver)

    def run(self):
        # register sockets for the clients and the workers
        poller = zmq.Poller()
        poller.register(self.router, zmq.POLLIN)
        poller.register(self.client, zmq.POLLIN)
    
        # store the worker ids and availabilities
        workers = {}

        # temp variables for testing communication
        best_score = float("-inf")
        best = ''
        num_moves = 0
        num_received = 0

        # queue to contain the tasks for the workers
        queue = []

        while True:
            # get lists of readable sockets
            socks = dict(poller.poll())

            # if WORKER has a message!
            if self.router in socks and socks[self.router] == zmq.POLLIN:
                w_id, c_id, message = self.router.recv_multipart()

                # worker ready
                if message == b"ready":
                    workers[w_id] = True
                    print("ya worker ready")

                # worker returned result    
                else:
                    workers[w_id] = False
                    score, board = message.decode().split(",")
                    num_received += 1


                    # this should be separated for each client (so use dictionary too)
                    score = int(score)
                    if score > best_score:
                        #print(score)
                        best = board
                        best_score = score
    
                    # need to count this but for all clients (so maybe dictionary)               
                    if num_received == num_moves:
                        print(best, best_score)
                        self.client.send_multipart([c_id, c_id, best.encode()])
                        

            # if CLIENT has a message!
            if self.client in socks and socks[self.client] == zmq.POLLIN:
                c_id, message = self.client.recv_multipart()
                
                # split up possible moves and add to task queue
                b = message.decode()
                board = chess.Board(fen=b)
                # need to change for mulit-client
                num_received = 0
                best_score = float('-inf')
                legal_moves = board.legal_moves
                num_moves = legal_moves.count()

                for move in board.pseudo_legal_moves:
                    if move in board.legal_moves:
                        queue.append((c_id, board, move))


            #print("queue: ", queue)
            
            # send tasks to workers
            if len(queue) > 0:
                for worker, available in workers.items():
                    if available:
                        client_id, board, message = queue.pop()
                        self.router.send_multipart([bytes(worker), bytes(client_id), board.fen().encode(), str(message).encode()])
                        
                        # worker no longer available until 'ready' again
                        workers[worker] = False
                    

    def update_nameserver(self, signum, frame):
        addrs = socket.getaddrinfo(NSERVER, NPORT, socket.AF_UNSPEC, socket.SOCK_DGRAM)
        for addr in addrs:
            ai_fam, stype, proto, name, sa = addr
            s = socket.socket(ai_fam, stype, proto)

            s.sendto(json.dumps({"type":"chessClient","owner":"MMBW","port":self.c_port,"project":"GREGChessApp"}).encode(), sa)
            s.sendto(json.dumps({"type":"chessWorker","owner":"MMBW","port":self.w_port,"project":"GREGChessApp"}).encode(), sa)
            s.close()
            break


# Main
def main():
    server = ChessServer()
    server.run()

if __name__ == "__main__":
    main()
