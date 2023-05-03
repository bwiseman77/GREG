#Greg Serverddid
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

# Functions
def usage(status):
    '''
    param:  status
    return: None
    Usage function that exits with STATUS
    '''
    print(f"Usage: ./GREGServer.py [options]")
    print(f"    -n NAME    Add unique name")
    print(f"    -d         Turn debugging on")
    print(f"    -h         help")
    exit(status)


# Classes 
class ChessServer:
    HEARTBEAT_LIVENESS = 3
    HEARTBEAT_INTERVAL = 5000 # msecs
    HEARTBEAT_EXPIRY = HEARTBEAT_INTERVAL * HEARTBEAT_LIVENESS
    POLL_TIMEOUT = 5000

    heartbeat_at = None

    #########################
    #    Class Functions    #
    #########################
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

        # set up name server pinging
        signal.setitimer(signal.ITIMER_REAL, 1, 60)
        signal.signal(signal.SIGALRM, self.update_nameserver)

        # worker structures
        self.workers = dict()
        self.waiting = []
        self.work_queue = []

        # client structures
        self.clients = dict()

        
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
            if self.debug:
                print(msg)


    def add_task(self, task):
        '''
        param:  task string: task to be added to the work queue
        return: None
        wrapper function to add task
        '''
        self.work_queue.append(task)

    def worker_req(self, worker_id):
        '''
        param:  worker_id string: worker id that has the req
        return: None
        wrapper to add ready worker to dict
        '''
        if worker_id in self.workers:
            # task not returned sadness
            task = self.workers[worker_id]['task']
            if task != '':
                self.add_task(task)
                self.printg(task)
    
        self.add_worker(worker_id, available=True)

    
    def returned_result(self, worker_id, client_id, move, score):
        '''
        param:  worker_id string: worker id that has result
        param:  client_id string: client id of job
        param:  move string:      result move
        param:  score int:        result score
        return: None
        Takes incoming messages and sends results back to client if all moves recieved
        Also trashes dead workers work and keeps track of clients best moves
        '''
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
        
            if self.clients[client_id]['received_moves'] == self.clients[client_id]['num_moves']:
                msg = json.dumps({"move":self.clients[client_id]['best_move'], "score":self.clients[client_id]['best_score']}).encode()
                
                
                self.printg(msg)
                self.client.send_multipart([client_id, client_id, msg])

        self.workers[worker_id]['available'] = False


    def add_worker(self, worker_id, available=False, alive=True, task='', expiry=0):
        '''
        param:  worker_id string: worker id recieved from message
        param:  available bool:   if worker is available
        param:  task string:      task to assign to worker
        param:  expiry int:       time till declared dead
        return: None
        adds worker structure
            available: bool: if worker is available
            expiry: float: expire time for worker to be considered dead
            alive: bool: if worker is alive
            task: string: task worker is working on
        '''
        self.workers[worker_id] = {
            'available': available,
            'alive': alive,
            'task': task,
            'expiry': expiry
        }


    def add_client(self, client_id, num_moves):
        '''
        param:  client_id string: client id received from message
        param:  num_moves int: number of moves/tasks to be recollected
        return: None
        adds client structure 
            alive: bool: client connected or not
            expiry: float: expire time for a client to be considered dead
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
        param:  worker_id string: worker to be marked as dead
        return: None
        Declares workers dead
        '''
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
        '''
        param:  signum Signal
        param:  frame Stackframe
        return: None
        Updates Nameserver with server name
        '''
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
        '''
        param:  is_worker bool: if ident is a worker
        param:  ident string:   id of a request
        return: None
        Updates expiry upon heartbeat
        '''
        if is_worker:
            self.workers[ident]['expiry'] = time.time() + 1e-3*self.HEARTBEAT_EXPIRY
            if ident in self.waiting:
                self.waiting.remove(ident)
            self.waiting.append(ident)
        else:
            self.clients[ident]['expiry'] = time.time() + 1e-3*self.HEARTBEAT_EXPIRY


    def purge_workers(self):
        '''
        param:  None
        return: None
        Purges dead workers
        '''
        while self.waiting:
            worker = self.waiting[0]
            # workers in order of expiry
            if self.workers[worker]['expiry'] < time.time():
                self.printg(f"delete expired worker {worker}")
                self.worker_die(worker)
                self.waiting.pop(0)
            else:
                break


    def purge_clients(self):
        '''
        param:  None
        return: None
        Purges dead clients
        '''
        for client, info in self.clients.items():
            if info['alive'] and info['expiry'] < time.time():
                self.printg(f"delete expired client {client}")
                self.clients[client]['alive'] = False

    
    def run(self):
        '''
        param:  None
        return: None
        Main loop of server, recvs messages from workers and clients and sends responses
        '''
        # register sockets for the clients and the workers
        poller = zmq.Poller()
        poller.register(self.worker, zmq.POLLIN)
        poller.register(self.client, zmq.POLLIN)

        # main loop
        while True:
            # get lists of readable sockets
            self.printg(self.work_queue)
            socks = dict(poller.poll())
 
            # if WORKER has a message!
            if self.worker in socks and socks[self.worker] == zmq.POLLIN:
                w_id, c_id, message = self.worker.recv_multipart()
                message = json.loads(message)
                self.printg(message)
                msg_type = message["type"]

                # worker ready
                if msg_type == "WorkerRequest":
                    self.worker_req(w_id)
                    self.printg("ya worker ready")
                elif msg_type == "<3":
                    self.printg("<3")
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
                    self.printg("client <3")
                    pass
                else:
                    self.printg(f"{c_id} {message}")

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
            
            self.printg("checking to send work")
            while len(self.work_queue) > 0 and len(available_workers) > 0:
                client_id, board, move, depth = self.work_queue.pop() 
                if self.clients[client_id]['alive']:       
                    worker = available_workers.pop()
                    msg = json.dumps({"listOfMoves":[move], "board":board.fen(),"depth":depth}).encode()
                    self.printg(msg)
                    self.workers[worker]['task'] = (client_id, board, move, depth)
                    self.worker.send_multipart([bytes(worker), bytes(client_id), msg])
                    
                    # worker no longer available until 'ready' again
                    self.workers[worker]['available'] = False
          
            self.purge_workers()
            self.purge_clients()


# Main Execution
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
