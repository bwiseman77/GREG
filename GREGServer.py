#Greg Server

import time
import zmq
import chess
import signal
import sys
import json
import socket

# Globals
NSERVER = "catalog.cse.nd.edu"
NPORT   = 9097

# Classes 
class ChessServer:
    def __init__(self, CPort=5000, WPort=5550):
        self.CPort = CPort
        self.WPort = WPort
        signal.setitimer(signal.ITIMER_REAL, 1, 60)
        signal.signal(signal.SIGALRM, self.update_nameserver)
        self.connect()

    def connect(self):
        # Client Socket
        self.context = zmq.Context()
        self.client = self.context.socket(zmq.ROUTER)
        self.client.bind(f"tcp://*:{self.CPort}")

        # Worker Socket 
        self.worker = self.context.socket(zmq.DEALER)
        self.worker.bind(f"tcp://*:{self.WPort}")

        zmq.device(zmq.QUEUE, self.client, self.worker)

    def run(self):
        while True:

            print("wtf")

            #  Wait for next request from client
            move = self.client.recv()
          
            print(move)

            # wait for worker to ask for data
            message = self.worker.recv()

            print(message)

            # ask worker to find move
            self.worker.send(move)

            # get move back
            move = self.worker.recv()

            print(move)

            #  Send reply back to client
            self.client.send(move)

    def update_nameserver(self, signum, frame):
        addrs = socket.getaddrinfo(NSERVER, NPORT, socket.AF_UNSPEC, socket.SOCK_DGRAM)
        for addr in addrs:
            ai_fam, stype, proto, name, sa = addr
            s = socket.socket(ai_fam, stype, proto)

            s.sendto(json.dumps({"type":"chessClientBrett","owner":"MMBW","port":self.CPort,"project":"GREGChessApp"}).encode(), sa)
            s.sendto(json.dumps({"type":"chessWorkerBrett","owner":"MMBW","port":self.WPort,"project":"GREGChessApp"}).encode(), sa)
            s.close()
            break


# Main
def main():
    server = ChessServer()
    server.run()

if __name__ == "__main__":
    main()
