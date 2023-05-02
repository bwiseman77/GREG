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
import socket

# Globals

GameOver = False
Result   = ""
NumMoves = 0

# Functions

def usage(status):
    '''Prints Usage message'''
    print(f"Usage: ./testChess.py [options]")
    print(f"    -b DEPTH    Depth of searches for black (depth = 1)")
    print(f"    -w DEPTH    Depth of searches for white (depth = 1)")
    print(f"    -n NAME     Add unique name")
    print(f"    -g GAMES    Number of Games to play")
    print(f"    -c COUNT    Number of workers")
    print(f"    -s H P      Server Host and Port")
    print(f"    -d          Debug")
    print(f"    -h          help")
    exit(status)

def spawn(num, port, host):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(json.dumps({"req":"spawn","numWorkers":f"{num}"}).encode(), (host, port))

def kill(port, host):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(json.dumps({"req":"kill"}).encode(), (host, port))

def get_move(proc, turn, debug):
    '''Gets move from a process'''
    global GameOver
    global Result
    global NumMoves

    # if game is over, dont do anything
    if GameOver:
        return

    # get the move
    if debug:
        print(f"getting move")
    move = proc.stdout.readline().decode().split()
    if debug:
        print(f"getting move for {turn}:{move}|")
    
    # add to total moves made
    NumMoves += 1

    # check of game ended
    if move[0] == "game":
        Result = " ".join(move)
        GameOver = True
        return

    return move[2] + "\n"

def make_move(proc, move, turn, debug):
    global GameOver

    # if game is over, dont do anything
    if GameOver:
        return

    if debug:
        print(f"making move for {turn}:{move}", end="")
   
    # read "make move" or possible "game over"
    proc.stdout.readline().decode()

    # write the move
    proc.stdin.write(move.encode())
    proc.stdin.flush()
    return

def play_game(black_depth=1, white_depth=1, name="", debug=False):
    ''' 
    plays a game of CPU vs CPU
    1. "black" gets the whites cpu move
    2. We then use "white" to send this move in and get the move black should play
    3. "white" then reads this move and "black" writes this.

    So, the "black" game is the main board, and black uses "white" to find out its own move.
    I know, kinda dumb and confusing but not really sure how else to phrase. Maybe "main" and "secondary"?
    '''
    
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
    white.wait()
    black.kill()
    black.wait()

    return

# Main Execution

def main():
    global GameOver
    global Result
    global NumMoves

    # options
    black_depth = "1"
    white_depth = "1"
    debug       = False
    name        = "test"
    num_games   = 1
    num_workers = 1
    argind      = 1
    host        = "student10.cse.nd.edu"
    port        = 7777
    
    # parse command args
    while argind < len(sys.argv):
        arg = sys.argv[argind]
        if arg == "-d":
            debug = True
        elif arg == "-n":
            argind += 1
            name = sys.argv[argind]
        elif arg == "-g":
            argind += 1
            num_games = int(sys.argv[argind])
        elif arg == "-c":
            argind += 1
            num_workers = int(sys.argv[argind])
        elif arg == "-s":
            argind += 1
            host = sys.argv[argind]
            argind += 1
            port = int(sys.argv[argind])
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

    # spawn workers
    spawn(num_workers, port, host)

    # run tests
    white_wins = 0
    black_wins = 0
    draws      = 0
    total_time = 0
    times      = []
    moves      = []
    games      = []
    for i in range(num_games):
        # reset variables
        start = time.time_ns()
        GameOver = False
        Result   = ""
        NumMoves = 0

        # play the game
        play_game(black_depth, white_depth, name, debug)
        
        # end
        total_time = time.time_ns() - start
        
        # collect data
        if "1-0" in Result:
            white_wins += 1
        elif "0-1"in Result:
            black_wins += 1
        elif "1/2-1/2" in Result:
            draws += 1

        games.append(Result)
        times.append(total_time)
        moves.append(NumMoves)

    # collect workers
    kill(port, host)

    # print data
    print(f"Workers   : {num_workers}")
    print(f"White Wins: {white_wins}")
    print(f"Black Wins: {black_wins}")
    print(f"Draws     : {draws}")
    print(f"Moves/sec : {sum(moves)/sum(times) * 1000000000}")
    print(f"All games:")
    for game in games:
        print(f"{game.split()[2]}")


    

if __name__ == "__main__":
    main()
