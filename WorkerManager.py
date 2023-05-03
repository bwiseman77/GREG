import sys
import socket
import subprocess
import json

# Functions

def setup(port):
    '''Set up socket'''
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('', port))
    print("listing on port", port)
    return s

def usage(status):
    '''Usage Function'''
    print(f"Usage: python WorkerManager.py [options]")
    print(f"    -p PORT    Port to listen on")
    print(f"    -n NAME    Unique name (default=test)")
    print(f"    -h         Help")
    exit(status)

# Main Execution

def main():
    # variables
    name        = "test"
    port        = 9000
    workers     = []
    doingWork   = False
    argind      = 1

    # parse ags
    while len(sys.argv) > argind:
        arg = sys.argv[argind]
        if arg == "-p":
            argind += 1
            port = int(sys.argv[argind])
        elif arg == "-n":
            argind += 1
            name = sys.argv[argind]
        elif arg == "-h":
            usage(0)
        else:
            usage(1)

        argind += 1
        
    # set up server 
    s = setup(port)

    # accept jobs
    while True:
        msg, addr = s.recvfrom(1024)
        msg = json.loads(msg)

        # spawn workers and dont spawn more until current job is done
        if msg["req"] == "spawn" and not doingWork:
            print("spawning workers")
            doingWork = True
            for _ in range(int(msg["numWorkers"])):
                w = subprocess.Popen(["python", "GREGWorker.py", "-n", name])
                workers.append(w)

        # kill and collect workers
        elif msg["req"] == "kill" and doingWork:
            doingWork = False
            print("killing workers")
            for w in workers:
                w.kill()
                w.wait()
        else:
            pass

if __name__ == "__main__":
    main()
