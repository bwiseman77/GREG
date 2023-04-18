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
    def __init__(self, Port=5555, CPort=5556, WPort=5557):
        self.Port = Port
        self.CPort = CPort
        self.WPort = WPort

        proxy_proc = Thread(target=self.proxy)
        proxy_proc.start()

        time.sleep(1)
        self.connect_client()

        # set up name server pinging
        #signal.setitimer(signal.ITIMER_REAL, 1, 60)
        #signal.signal(signal.SIGALRM, self.update_nameserver)

    def connect_client(self):
        self.context = zmq.Context()
        
        # Client Socket 
        self.client = self.context.socket(zmq.REP)
        self.client.bind(f"tcp://*:{self.CPort}")

        # connection to proxy
        self.proxy_socket = self.context.socket(zmq.ROUTER)

        self.proxy_socket.connect("tcp://127.0.0.1:5559")#f"inproc://please")



    def proxy(self):
        # Router Socket (to get messages from main server process)
        context = zmq.Context()
        server = context.socket(zmq.ROUTER)
        server.bind("tcp://127.0.0.1:5559")#f"inproc://please")


        print("maybe? lets recv")
        message = server.recv()
        print("yes i finally got a message!", message)

        # Worker Socket 
        worker = context.socket(zmq.DEALER)
        worker.bind(f"tcp://*:{self.WPort}")
        #self.worker.send_string("hello")

        try:
            print("proxy starting")
            zmq.proxy(server, worker)
        except KeyboardInterrupt:
            return


    def run(self):


        poller = zmq.Poller()
        poller.register(self.client, zmq.POLLIN)
        poller.register(self.proxy_socket, zmq.POLLIN)

        socket = self.proxy_socket
        client = self.client
   

        while True:
            socks = dict(poller.poll())
            if socket in socks and socks[socket] == zmq.POLLIN:
                message = socket.recv(zmq.DONTWAIT)
                print("message is ", message)

                
                
            if client in socks and socks[client] == zmq.POLLIN:
                message = client.recv(zmq.DONTWAIT)
                print("client sent ", message)
                print("socks:", socks)

                print("proxy socket", self.proxy_socket)
                self.proxy_socket.send(message)
                #socket.send_string("hellooooo")
                print("sent message!")
            

        proxy_proc.terminate()




    def update_nameserver(self, signum, frame):
        addrs = socket.getaddrinfo(NSERVER, NPORT, socket.AF_UNSPEC, socket.SOCK_DGRAM)
        for addr in addrs:
            ai_fam, stype, proto, name, sa = addr
            s = socket.socket(ai_fam, stype, proto)

            s.sendto(json.dumps({"type":"chessClient","owner":"MMBW","port":self.CPort,"project":"GREGChessApp"}).encode(), sa)
            s.sendto(json.dumps({"type":"chessWorker","owner":"MMBW","port":self.WPort,"project":"GREGChessApp"}).encode(), sa)
            s.close()
            break


# Main
def main():
    server = ChessServer()
    server.run()

if __name__ == "__main__":
    main()
