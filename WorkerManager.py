import sys
import socket
import subprocess
import json

def setup(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('', port))
    print("listing on port", port)
    return s

def usage(status):
    print(f"Usage: python WorkerManager.py port name")
    exit(status)

def main():
    name        = "test"
    port        = int(sys.argv[1])
    workers     = []
    doingWork   = False
    if len(sys.argv) == 3:
        name        = sys.argv[2]
     
    s = setup(port)

    while True:
        msg, addr = s.recvfrom(1024)
        msg = json.loads(msg)

        if msg["req"] == "spawn" and not doingWork:
            print("spawning workers")
            doingWork = True
            for _ in range(int(msg["numWorkers"])):
                w = subprocess.Popen(["python", "GREGWorker.py", "-n", name])
                workers.append(w)

        elif msg["req"] == "kill" and doingWork:
            doingWork = False
            print("killing workers")
            for w in workers:
                w.kill()
                w.kill()
        else:
            pass

if __name__ == "__main__":
    main()
