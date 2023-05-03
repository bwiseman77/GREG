# GREG

## Setup

For the Project we used a stockfish binary (located in bin) and used the chess python and zmq module, and we are using python version 3.9.5:

  `pip3 install chess`\
  `pip3 install zmq`

## Running Code

### Player vs CPU
For the code to run, you need to have a GREGServer, at least one GREGWorker, and a GREGClient. Each python script has help functions to show different running options (`python $PROGRAM -h`)

Example:\
`python GREGServer.py`\
`python GREGClient.py`\
`python GREGWorker.py`

<img width="1451" alt="Screen Shot 2023-05-03 at 1 52 34 PM" src="https://user-images.githubusercontent.com/72280180/236002647-88ee30e0-d5ea-4251-89ae-83a04af53f45.png">

### CPU vs CPU
To run simulations of CPU vs CPU, we have GREGSimulator.py which takes arguments to play CPUs against each other. It can be used with WorkerManager.py to help spawn in workers, but each needs to be sure to have the same `-n $NAME` flag set so it knows which server to connect to. It is important to note that server must be started, then worker manager, then simulator.

Example:\
`python GREGSimulator.py  -s student10.cse.nd.edu 9000 -b 1 -w 1 -n demo -c 20`\
`python WorkerManager.py -n demo`\
`python GREGServer.py -n demo`

<img width="1454" alt="Screen Shot 2023-05-03 at 1 56 32 PM" src="https://user-images.githubusercontent.com/72280180/236003512-b7da7448-c33d-4f1e-b192-4a74fd49c78c.png">

Final Project for CSE-40771

Distributed Chess Application Service

Mia Manabat and Brett Wiseman
