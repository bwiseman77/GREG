# GREG Client
import zmq
import chess
import sys

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")

def main():

    print("Welcome to the GREG chess application! (q to quit)")
    board = chess.Board()
        

    while(True):
        print(board)
        if board.is_checkmate():
            print(f"game over! {board.outcome().result()}")
            exit(0)
        move = input("Make your move (uci): \n")
        if move == "q":
            print("Ending Game")
            exit(0)
        
        try:
            move = chess.Move.from_uci(move)
        except:
            print("please make a valid move")
            continue

        if move not in board.legal_moves:
            print("please make a valid move")
            continue

        board.push(move)

        # get next move from server
        b = board.fen()
        socket.send(bytes(b, "utf-8"))

        move = socket.recv().decode("utf-8")
        move = chess.Move.from_uci(move)
        board.push(move)
        


if __name__ == "__main__":
    main()
