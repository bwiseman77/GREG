#Greg Server

import time
import zmq
import chess

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

while True:
    #  Wait for next request from client
    message = socket.recv()
    print(f"{message}")

    b = message.decode("utf-8")
    board = chess.Board(fen=b)
    print(board)
    #  Do some 'work'
    while True:
        move = input("Make your move (uci): \n")
        if chess.Move.from_uci(move) in board.legal_moves:
            break
        
    #  Send reply back to client
    socket.send(bytes(move,"utf-8"))
