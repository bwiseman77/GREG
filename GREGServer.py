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
    HEARTBEAT_INTERVAL = 5000 # msecs
    HEARTBEAT_EXPIRY = HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS
    POLL_TIMEOUT = 5000

    heartbeat_at = None

    def __init__(self, debug=False, name=""):
        self.debug   = debug
        self.name    = name

        self.heartbeat_at = time.time() + 1e-3*self.HEARTBEAT_INTERVAL

        # create zmq context
        self.context = zmq.Context()
        self.worker  = self.context.socket(zmq.ROUTER)
        self.client  = self.context.socket(zmq.ROUTER)
        
        # bind to random port
        self.w_port  = self.worker.bind_to_random_port(f"tcp://*")
        self.c_port  = self.client.bind_to_random_port(f"tcp://*")

        if debug:
            print(self.c_port, self.w_port)

        # set up name server pinging
        signal.setitimer(signal.ITIMER_REAL, 1, 60)
        signal.signal(signal.SIGALRM, self.update_nameserver)

        self.workers = dict()
        self.waiting = []
        self.work_queue = []

        self.clients = dict()
        
    def add_task(self, task):
        '''
        task: param string: task to be added to the work queue
        wrapper function to add task
        '''
        self.work_queue.append(task)

    def worker_req(self, worker_id):
        '''
        worker_id: param string: worker id that has the req
        '''
        if worker_id in self.workers:
            # task not returned sadness
            task = self.workers[worker_id]['task']
            print('task !!', task)
            if task != '':
                self.add_task(task)
                if self.debug:
                    print(task)
    
        self.add_worker(worker_id, available=True)

    
    def returned_result(self, worker_id, client_id, move, score):
        # if dead, trash results, now alive again!
        if not self.workers[worker_id]['alive']:
            self.workers[worker_id]['alive'] = True
            self.workers[worker_id]['task'] = ''
        else:
            self.clients[client_id]['received_moves'] += 1
            self.workers[worker_id]['task'] = ''
            if score != float('-inf'):
                score = int(score)

                if score > self.clients[client_id]['best_score']: 
                    self.clients[client_id]['best_move'] = move
                    self.clients[client_id]['best_score'] = score
        
            print("client moves", client_id, self.clients[client_id]['received_moves'], self.clients[client_id]['num_moves'])
            if self.clients[client_id]['received_moves'] == self.clients[client_id]['num_moves']:
                msg = json.dumps({"move":self.clients[client_id]['best_move'], "score":self.clients[client_id]['best_score']}).encode()
                
                
                if self.debug:
                    print(msg)
                self.client.send_multipart([client_id, client_id, msg])

        self.workers[worker_id]['available'] = False

        

    def add_worker(self, worker_id, available=False, alive=True, task='', expiry=0):
        '''
        worker_id:...... to be finished
        '''
        self.workers[worker_id] = {
            'available': available,
            'alive': alive,
            'task': task,
            'expiry': expiry
        }


    def add_client(self, client_id, num_moves):
        '''
        client_id: param string: client id received from message
        num_moves: param int: number of moves/tasks to be recollected
        
        adds client structure 
            alive: bool: client connected or not
            expiry: float: expire time for a worker to be considered dead
            best_move: string: the current best move returned by a worker based on score
            num_moves: int: number of moves/tasks to be recollected at that time
            received_moves: int: num of moves currently received
        '''

        self.clients[client_id] = {
            'alive': True,
            'expiry': 0,
            'best_move': '',
            'best_score': float('-inf'),
            'num_moves': num_moves,
            'received_moves': 0
        }

    def worker_die(self, worker_id):
        '''
        worker_id: param string: worker to be marked as dead
        '''
        # check if there was work assigned
        print("worker died ya", worker_id)
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

            s.sendto(json.dumps({"type":f"{self.name}chessClient","owner":"MMBW","port":self.c_port,"project":"GREGChessApp"}).encode(), sa)
            s.sendto(json.dumps({"type":f"{self.name}chessWorker","owner":"MMBW","port":self.w_port,"project":"GREGChessApp"}).encode(), sa)
            s.close()
            break

    
    def update_expiry(self, is_worker, ident):
        if is_worker:
            self.workers[ident]['expiry'] = time.time() + 1e-3*self.HEARTBEAT_EXPIRY
            if ident in self.waiting:
                self.waiting.remove(ident)
            self.waiting.append(ident)
        else:
            self.clients[ident]['expiry'] = time.time() + 1e-3*self.HEARTBEAT_EXPIRY


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


    def purge_clients(self):
        for client, info in self.clients.items():
            if info['alive'] and info['expiry'] < time.time():
                print("delete expired client", client)
                self.clients[client]['alive'] = False


    def run(self):
        # register sockets for the clients and the workers
        poller = zmq.Poller()
        poller.register(self.worker, zmq.POLLIN)
        poller.register(self.client, zmq.POLLIN)

        # main loop
        while True:
            # get lists of readable sockets
           # try:
            if self.debug:
                print(self.work_queue)
            socks = dict(poller.poll())
            #if self.debug:
            #    print(socks)
            #except KeyboardInterrupt:
            #    break

            # if WORKER has a message!
            if self.worker in socks and socks[self.worker] == zmq.POLLIN:
                w_id, c_id, message = self.worker.recv_multipart()
                print('worker id, client id, message', w_id, c_id, message)
                message = json.loads(message)
                if self.debug:
                    print(message)
                msg_type = message["type"]

                # worker ready
                if msg_type == "WorkerRequest":
                    self.worker_req(w_id)
                    if self.debug:
                        print("ya worker ready")
                elif msg_type == "<3":
                    if self.debug:
                        print("<3")
                    pass

                # worker returned result    
                else:
                    move  = message["move"]
                    score = message["score"]
                    self.returned_result(w_id, c_id, move, score)

                # update expiry time
                if w_id in self.workers:
                    self.update_expiry(is_worker=True, ident=w_id)

            # if CLIENT has a message!
            if self.client in socks and socks[self.client] == zmq.POLLIN:
                # read and parse message
                c_id, message = self.client.recv_multipart()
                message       = json.loads(message.decode())
                
                if message.get("type") == "<3":
                    if self.debug:
                        print("client <3")
                    pass
                else:
                    if self.debug:
                        print(c_id, message)

                    b     = message["board"]
                    depth = message["depth"]

                    board = chess.Board(fen=b)
                    
                    legal_moves = board.legal_moves
                    num_moves = legal_moves.count()

                    # split up possible moves and add to task queue
                    for move in board.pseudo_legal_moves:
                        if move in board.legal_moves:
                            self.add_task((c_id, board, move.uci(), depth))
                
                    self.add_client(c_id, num_moves=num_moves)
                
                if c_id in self.clients:
                    self.update_expiry(is_worker=False, ident=c_id)
            
            # send tasks to workers
            available_workers = [x for x in self.workers if self.workers[x]['available'] and self.workers[x]['alive']]
            
            if self.debug:
                print("checking to send work")
            while len(self.work_queue) > 0 and len(available_workers) > 0:
                client_id, board, move, depth = self.work_queue.pop() 
                if self.clients[client_id]['alive']:       
                    worker = available_workers.pop()
                    msg = json.dumps({"listOfMoves":[move], "board":board.fen(),"depth":depth}).encode()
                    if self.debug:
                        print(msg)
                    self.workers[worker]['task'] = (client_id, board, move, depth)
                    self.worker.send_multipart([bytes(worker), bytes(client_id), msg])
                    
                    # worker no longer available until 'ready' again
                    self.workers[worker]['available'] = False
          
            self.purge_workers()
            self.purge_clients()


def usage(status):
    print(f"Usage: ./GREGServer.py [options]")
    print(f"    -n NAME    Add unique name")
    print(f"    -d         Turn debugging on")
    print(f"    -h         help")
    exit(status)


# Main
def main():
    # options
    debug  = False
    name   = ""
    argind = 1
    
    # parse args
    while argind < len(sys.argv):
        arg = sys.argv[argind]

        if arg == "-d":
            debug = True
        elif arg == "-n":
            argind += 1
            name = sys.argv[argind]
        elif arg == "-h":
            usage(0)
        else:
            usage(1)
        argind += 1


    # run game
    server = ChessServer(debug, name)
    server.run()

if __name__ == "__main__":
    main()
