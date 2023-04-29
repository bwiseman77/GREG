#Greg Server

import time
import zmq
import zmq.utils.monitor
import chess
import signal
import sys
import json
import socket
from threading import Lock

# Globals
NSERVER = "catalog.cse.nd.edu"
NPORT   = 9097

# Classes 
class ChessServer:
    
    HEARTBEAT_LIVENESS = 3
    HEARTBEAT_INTERVAL = 2500 # msecs
    HEARTBEAT_EXPIRY = HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS

    heartbeat_at = None



    def __init__(self):
        self.heartbeat_at = time.time() + 1e-3*self.HEARTBEAT_INTERVAL

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

        self.workers = dict()
        self.waiting = []
        self.work_queue = []


        self.best_move = ''
        self.best_score = float('-inf')
        self.num_moves = 0
        self.move_count = 0


    def add_task(self, task):
        self.work_queue.append(task)


    def worker_req(self, worker_id, available=False):
        if worker_id in self.workers:
            # task not returned sadness
            task = self.workers[worker_id]['task']
            if task != '':
                self.add_task(task)
    
        self.add_worker(worker_id, available)

    
    def returned_result(self, worker_id, client_id, move, score):
        # if dead, trash results, now alive again!
        if not self.workers[worker_id]['alive']:
            self.workers[worker_id]['alive'] = True
        else:
            self.move_count += 1
            score = int(score)
            if score > self.best_score:
                self.best_move = move
                self.best_score = score

            if self.move_count == self.num_moves:
                print(self.best_move, self.best_score)
                msg = json.dumps({"move":self.best_move, "score":self.best_score}).encode()
                self.client.send_multipart([client_id, client_id, msg])

        self.workers[worker_id]['available'] = False

        

    def add_worker(self, worker_id, available=False, alive=True, task='', expiry=0):
        self.workers[worker_id] = {
            'available': available,
            'alive': alive,
            'task': task,
            'expiry': expiry
        }


    def worker_die(self, worker_id):
        # check if there was work assigned
        task = self.workers[worker_id]['task']

        # redistribute work
        if task != '':
            self.work_queue.append(task)
            self.workers[worker_id]['task'] = ''

        # mark worker as dead and not available
        self.workers[worker_id]['available'] = False
        self.workers[worker_id]['alive'] = False

    


    def update_nameserver(self, signum, frame):
        addrs = socket.getaddrinfo(NSERVER, NPORT, socket.AF_UNSPEC, socket.SOCK_DGRAM)
        for addr in addrs:
            ai_fam, stype, proto, name, sa = addr
            try:
                s = socket.socket(ai_fam, stype, proto)
            except:
                continue

            s.sendto(json.dumps({"type":"MiachessClient","owner":"MMBW","port":self.c_port,"project":"GREGChessApp"}).encode(), sa)
            s.sendto(json.dumps({"type":"MiachessWorker","owner":"MMBW","port":self.w_port,"project":"GREGChessApp"}).encode(), sa)
            s.close()
            break

    
    def run(self):
        # register sockets for the clients and the workers
        poller = zmq.Poller()
        poller.register(self.worker, zmq.POLLIN)
        poller.register(self.client, zmq.POLLIN)
    

        # main loop
        while True:
            # get lists of readable sockets
            try:
                socks = dict(poller.poll(self.HEARTBEAT_INTERVAL))
                print(socks)
            except KeyboardInterrupt:
                break

            # if WORKER has a message!
            if self.worker in socks and socks[self.worker] == zmq.POLLIN:
                w_id, c_id, message = self.worker.recv_multipart()
                message = json.loads(message)
                msg_type = message["type"]

                # worker ready
                if msg_type == "WorkerRequest":
                    self.worker_req(w_id, True)
                    print("ya worker ready")

                # worker returned result    
                else:
                    move  = message["move"]
                    score = message["score"]
                    self.returned_result(w_id, c_id, move, score)

                # update expiry time
                        

            # if CLIENT has a message!
            if self.client in socks and socks[self.client] == zmq.POLLIN:
                # read and parse message
                c_id, message = self.client.recv_multipart()
                message       = json.loads(message.decode())

                b     = message["board"]
                depth = message["depth"]

                board = chess.Board(fen=b)
                
                # need to change for multi-client
                self.move_count = 0
                self.best_score = float('-inf')
                legal_moves = board.legal_moves
                self.num_moves = legal_moves.count()

                # split up possible moves and add to task queue
                for move in board.pseudo_legal_moves:
                    if move in board.legal_moves:
                        self.add_task((c_id, board, move.uci(), depth))
            
            # send tasks to workers
            if len(self.work_queue) > 0:
                for worker, info in self.workers.items():
                    if info['available'] and info['alive']:
                        client_id, board, move, depth = self.work_queue.pop()
                        msg = json.dumps({"listOfMoves":[move], "board":board.fen(),"depth":depth}).encode()
                        self.worker.send_multipart([bytes(worker), bytes(client_id), msg])
                        
                        # worker no longer available until 'ready' again
                        self.workers[worker]['available'] = False
      
            self.send_heartbeats()

        def send_heartbeats(self):
            if time.time() > self.heartbeat_at:
                for worker in self.waiting:
                    self.worker.send_multipart([bytes(worker), bytes('<3')])
                self.heartbeat_at = time.time() + 1e-3*self.HEARTBEAT_INTERVAL

        def purge_workers(self):
            while self.waiting:
                w = self.waiting[0]
                # workers in order of expiry
                if self.workers[w]['expiry'] < time.time():
                    print("delete expired worker")
                    self.worker_die(w)
                    self.waiting.pop(0)
                else:
                    break


# Main
def main():
    server = ChessServer()
    server.run()

if __name__ == "__main__":
    main()
