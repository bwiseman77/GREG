# GREG Client
import zmq
import zmq.utils.monitor
import chess
import sys
import http.client
import json
import time
import signal
import os
import subprocess

# Globals

GameOver = False


# Functions

def usage(status):

    print(f"Usage: ./testChess.py [options]")
    print(f"    -d DEPTH    Depth of searches (depth = 1)")
    print(f"    -n NAME     Add unique name")
    print(f"    -h          help")

    exit(status)

def get_move(proc, turn, debug):
    global GameOver

    # if game is over, dont do anything
    if GameOver:
        return -1

    # get the move
    move = proc.stdout.readline().decode().split()
    if debug:
        print(f"getting move for {turn}:{move}|")

    # check of game ended
    if move[0] == "game":
        print(" ".join(move))
        GameOver = True
        return -1

    return move[2] + "\n"

def make_move(proc, move, turn, debug):
    global GameOver

    # if game is over, dont do anything
    if GameOver:
        return -1

    if debug:
        print(f"making move for {turn}:{move}", end="")
   
    # read "make move" or possible "game over"
    proc.stdout.readline().decode()

    # write the move
    proc.stdin.write(move.encode())
    proc.stdin.flush()
    return True

# Main Execution

def main():
    global GameOver
    # options
    black_depth = "1"
    white_depth = "1"
    debug       = False
    name        = "test"
    argind      = 1
    
    # parse command args
    while argind < len(sys.argv):
        arg = sys.argv[argind]
        if arg == "-d":
            depth = True
        elif arg == "-n":
            argind += 1
            name = sys.argv[argind]
        elif arg == "-b":
            argind += 1
            black_depth = sys.argv[argind]
        elif arg == "-w":
            argind += 1
            white_depth = sys.argv[argind]
        elif arg == "-h":
            usage(0)
        else:
            usage(1)
        argind += 1
    
    # play a game of CPU vs CPU
    # 1. "black" gets the whites cpu move
    # 2. We then use "white" to send this move in and get the move black should play
    # 3. "white" then reads this move and "black" writes this.

    # So, the "black" game is the main board, and black uses "white" to find out its own move.
    # I know, kinda dumb and confusing but not really sure how else to phrase. Maybe "main" and "secondary"?


    # start players
    black = subprocess.Popen(["python", "./GREGClient.py", "-d", black_depth, "-n", name, "-b", "-s"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    white = subprocess.Popen(["python", "./GREGClient.py", "-d", white_depth, "-n", name, "-s"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # play game
    while not GameOver:
        # get move from white cpu
        white_move = get_move(black, "black", debug)

        # send that move to white to get see what black should play
        make_move(white, white_move, "white", debug)

        # read blacks response from white
        black_move = get_move(white, "white", debug)

        # write blacks move to white
        make_move(black, black_move, "black", debug)

    # collect
    white.kill()
    black.kill()

if __name__ == "__main__":
    main()
