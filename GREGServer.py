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
    def __init__(self):
        # create zmq context
        self.context = zmq.Context()
        self.worker  = self.context.socket(zmq.ROUTER)
        self.client  = self.context.socket(zmq.ROUTER)
        
        # bind to random port
        self.w_port  = self.worker.bind_to_random_port(f"tcp://*")
        self.c_port  = self.client.bind_to_random_port(f"tcp://*")

        print(self.c_port, self.w_port)

        # set up name server pinging
        signal.setitimer(signal.ITIMER_REAL, 1, 60)
        signal.signal(signal.SIGALRM, self.update_nameserver)
    
    def update_nameserver(self, signum, frame):
        addrs = socket.getaddrinfo(NSERVER, NPORT, socket.AF_UNSPEC, socket.SOCK_DGRAM)
        for addr in addrs:
            ai_fam, stype, proto, name, sa = addr
            try:
                s = socket.socket(ai_fam, stype, proto)
            except:
                continue

            s.sendto(json.dumps({"type":"chessClient","owner":"MMBW","port":self.c_port,"project":"GREGChessApp"}).encode(), sa)
            s.sendto(json.dumps({"type":"chessWorker","owner":"MMBW","port":self.w_port,"project":"GREGChessApp"}).encode(), sa)
            s.close()
            break


    def run(self):
        # register sockets for the clients and the workers
        poller = zmq.Poller()
        poller.register(self.worker, zmq.POLLIN)
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

        # main loop
        while True:
            # get lists of readable sockets
            socks = dict(poller.poll())

            # if WORKER has a message!
            if self.worker in socks and socks[self.worker] == zmq.POLLIN:
                w_id, c_id, message = self.worker.recv_multipart()
                message = json.loads(message)

                msg_type = message["type"]
                # worker ready
                if msg_type == "WorkerRequest":
                    workers[w_id] = True
                    print("ya worker ready")

                # worker returned result    
                else:
                    move  = message["move"]
                    score = message["score"]
                    workers[w_id] = False
                    num_received += 1


                    # this should be separated for each client (so use dictionary too)
                    score = int(score)
                    if score > best_score:
                        #print(score)
                        best = move
                        best_score = score
    
                    # need to count this but for all clients (so maybe dictionary)               
                    if num_received == num_moves:
                        print(best, best_score)
                        msg = json.dumps({"move":best, "score":best_score}).encode()
                        self.client.send_multipart([c_id, c_id, msg])
                        

            # if CLIENT has a message!
            if self.client in socks and socks[self.client] == zmq.POLLIN:
                # read and parse message
                c_id, message = self.client.recv_multipart()
                message       = json.loads(message.decode())

                b     = message["board"]
                depth = message["depth"]

                board = chess.Board(fen=b)
                
                # need to change for mulit-client
                num_received = 0
                best_score = float('-inf')
                legal_moves = board.legal_moves
                num_moves = legal_moves.count()

                # split up possible moves and add to task queue
                for move in board.pseudo_legal_moves:
                    if move in board.legal_moves:
                        queue.append((c_id, board, move.uci(), depth))


            #print("queue: ", queue)
            
            # send tasks to workers
            if len(queue) > 0:
                for worker, available in workers.items():
                    if available:
                        client_id, board, move, depth= queue.pop()
                        msg = json.dumps({"listOfMoves":[move], "board":board.fen(),"depth":depth}).encode()
                        self.worker.send_multipart([bytes(worker), bytes(client_id), msg])
                        
                        # worker no longer available until 'ready' again
                        workers[worker] = False
                    


# Main
def main():
    server = ChessServer()
    server.run()

if __name__ == "__main__":
    main()
