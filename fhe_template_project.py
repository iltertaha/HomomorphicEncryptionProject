from eva import EvaProgram, Input, Output, evaluate
from eva.ckks import CKKSCompiler
from eva.seal import generate_keys
from eva.metric import valuation_mse
import timeit
import networkx as nx
from random import random
import matplotlib.pyplot as plt
import numpy as np
import csv

##### GLOBAL VARIABLES #### 

# ARRAYS
visitedArray = []
decryptedPrevAdjMatrix = []
queue = []
res = []

# FLAGS
initialize = notDone = True

# OTHER
vector_size = 4096
nodeCount = 0
eps = 0.4

############################


def BreadFirstTraversal(graph, s, nodeCount):
    try:
        res = []
        visitedArray = [False for i in range(nodeCount)]
        queue = [s]

        while len(queue):
            print(queue)

            # At each iteration, pop the element at the beginning of the queue
            elem = queue.pop(0)

            # Update visitedArray array
            if not visitedArray[elem]:
                visitedArray[elem] = True
                res.append(elem)

            # Add adjacent nodes of the current element
            for i in range(nodeCount):
                # add elem to the queue 
                # if elem does not exist in the queue and not visitedArray
                # and if elem is reachable from the current node
                if not visitedArray[i] and queue.count(i) == 0 and graph[elem * nodeCount + i] == 1:
                    queue.append(i)

        print("BFS Traversal: " + str(res)) 
    except:
        # in case any error occurs
        return -1

    # success
    return 1



# Using networkx, generate a random graph
# You can change the way you generate the graph
def generateGraph(n, k, p):
    #ws = nx.cycle_graph(n)
    ws = nx.watts_strogatz_graph(n,k,p)
    return ws

# If there is an edge between two vertices its weight is 1 otherwise it is zero
# You can change the weight assignment as required
# Two dimensional adjacency matrix is represented as a vector
# Assume there are n vertices
# (i,j)th element of the adjacency matrix corresponds to (i*n + j)th element in the vector representations
def serializeGraphZeroOne(GG,vec_size):
    n = GG.size()
    graphdict = {}
    g = []
    for row in range(n):
        for column in range(n):
            if GG.has_edge(row, column) or row==column:
                weight = 1
            else:
                weight = 0 
            g.append( weight  )  
            key = str(row)+'-'+str(column)
            graphdict[key] = [weight] # EVA requires str:listoffloat
    # EVA vector size has to be large, if the vector representation of the graph is smaller, fill the eva vector with zeros
    for i in range(vec_size - n*n): 
        g.append(0.0)
    return g, graphdict

# To display the generated graph
def printGraph(graph,n):
    for row in range(n):
        for column in range(n):
            print("{:.2f}".format(graph[row*n+column]), end = '\t')
        print() 

# Eva requires special input, this function prepares the eva input
# Eva will then encrypt them
def prepareInput(n, m):
    input = {}
    GG = generateGraph(n,3,0.5)
    serializedGraph, graphdict = serializeGraphZeroOne(GG,m)
    printGraph(serializedGraph,n)
    input['Graph'] = serializedGraph
    return input, serializedGraph

# Check adjacency matrix for reachable elements from the origin
def maskReachableItemsInMatrix(graph, origin, nodeCount):
    adjMatrix = [0] * vector_size
    selectedNode = 0

    for i in range(nodeCount):
        if queue.count(i) == 0 and not visitedArray[i]:    
            # Imagine serialized 2D vector
            temp = [1 if j == selectedNode else 0 for j in range(vector_size)]  
            adjMatrix += (graph<< (origin * nodeCount + i - selectedNode)) * temp
            selectedNode += 1

    return adjMatrix

def updateDecryptedAdjMatrix(outputs):
    global nodeCount
    global decryptedPrevAdjMatrix
    global eps

    for i in outputs:
        for j in range(nodeCount):
            # Use eps value for floating comparison
            checkPrevResultIsOne = (outputs[i][j] < 1.00 + eps) and (outputs[i][j] > 1.00 - eps)
            decryptedPrevAdjMatrix.append(True) if checkPrevResultIsOne else decryptedPrevAdjMatrix.append(False)


def initAdjacencyMatrix( start, nodeCount, graph):
    global initialize
    if(initialize):
        initialize = False
        queue.append(0)
        adjMatrix = maskReachableItemsInMatrix(graph, 0, nodeCount)
        return 1, adjMatrix
    else:
        return 0, []

# This is the dummy analytic service
# You will implement this service based on your selected algorithm
# you can other parameters using global variables !!! do not change the signature of this function
# 
# Note that you cannot compute everything using EVA/CKKS
# For instance, comparison is not possible
# You can add, subtract, multiply, negate, shift right/left
# You will have to implement an interface with the trusted entity for comparison (send back the encrypted values, push the trusted entity to compare and get the comparison output)
def graphanalticprogram(graph):
    
    global notDone
    global nodeCount
    global decryptedPrevAdjMatrix
    global initialize
    global queue
    global visitedArray

    # initialize adjacency matrix starting from node 0 
    returned, adjMatrix = initAdjacencyMatrix( 0, nodeCount, graph)
    if returned:
       return adjMatrix 

    # start from here if node is not zeroth node
    
    origin = queue[0]
    curr = 0
    
    print("queue:" + str(queue))
    if not visitedArray[origin]:
        visitedArray[origin] = True
        res.append(origin)
        # Remove first element from queue
        queue.pop(0)


    for i in range(nodeCount):
        
        if not visitedArray[i] and queue.count(i) == 0:
            # reachable from the prev iteration
            if decryptedPrevAdjMatrix[curr]:
                queue.append(i)

            curr += 1

    if len(queue) == 0:
        return maskReachableItemsInMatrix(graph, origin, nodeCount)
    else:
        notDone = False
        return res  
        


# Do not change this 
# the parameter n can be passed in the call from simulate function
class EvaProgramDriver(EvaProgram):
    def __init__(self, name, vec_size=4096, n=4):
        self.n = n
        super().__init__(name, vec_size)

    def __enter__(self):
        super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        super().__exit__(exc_type, exc_value, traceback)


# Repeat the experiments and show averages with confidence intervals
# You can modify the input parameters
# n is the number of nodes in your graph
# If you require additional parameters, add them
def simulate(n):
    global notDone
    global visitedArray
    global nodeCount
    global res
    global eps
    global initialize
    global decryptedPrevAdjMatrix
    
    m = vector_size
    print("Will start simulation for ", n)
    config = {}
    config['warn_vec_size'] = 'false'
    config['lazy_relinearize'] = 'true'
    config['rescaler'] = 'always'
    config['balance_reductions'] = 'true'
    inputs, g= prepareInput(n, m)

    
    nodeCount = n
    initialize = notDone = True
    totalCompiletime = totalKeygenerationtime  = totalEncryptiontime = 0
    totalExecutiontime = totalDecryptiontime = totalReferenceexecutiontime = 0
    totalMse = 0
    res = []
    queue = []
    visitedArray = []

    isSuccess = BreadFirstTraversal(g, 0, n)
    if(not isSuccess):
        raise Exception("BFS Algorithm failed.")

    
    # Clear and init all nodes as not visited
    visitedArray = [False] * nodeCount

    while notDone:

        graphanaltic = EvaProgramDriver("graphanaltic", vec_size=m,n=n)
        with graphanaltic:
            graph = Input('Graph')
            reval = graphanalticprogram(graph)
            Output('ReturnedValue', reval)
    
        prog = graphanaltic
        prog.set_output_ranges(30)
        prog.set_input_scales(30)

        start = timeit.default_timer()
        compiler = CKKSCompiler(config=config)
        compiled_multfunc, params, signature = compiler.compile(prog)
        totalCompiletime += (timeit.default_timer() - start) * 1000.0 #ms

        start = timeit.default_timer()
        public_ctx, secret_ctx = generate_keys(params)
        totalKeygenerationtime = (timeit.default_timer() - start) * 1000.0 #ms
    
        start = timeit.default_timer()
        encInputs = public_ctx.encrypt(inputs, signature)
        totalEncryptiontime += (timeit.default_timer() - start) * 1000.0 #ms

        start = timeit.default_timer()
        encOutputs = public_ctx.execute(compiled_multfunc, encInputs)
        totalExecutiontime += (timeit.default_timer() - start) * 1000.0 #ms

        start = timeit.default_timer()
        outputs = secret_ctx.decrypt(encOutputs, signature)
        totalDecryptiontime += (timeit.default_timer() - start) * 1000.0 #ms

        decryptedPrevAdjMatrix.clear()

        # Check previous adjacency matrix values and update the boolean matrix for next iteration
        
        updateDecryptedAdjMatrix(outputs) 
                
        start = timeit.default_timer()
        reference = evaluate(compiled_multfunc, inputs)
        totalReferenceexecutiontime += (timeit.default_timer() - start) * 1000.0 #ms

 
        totalMse += valuation_mse(outputs, reference) # since CKKS does approximate computations, this is an important measure that depicts the amount of error

    return totalCompiletime, totalKeygenerationtime, totalEncryptiontime, totalExecutiontime, totalDecryptiontime, totalReferenceexecutiontime, totalMse
 


if __name__ == "__main__":
    simcnt = 5 #The number of simulation runs, set it to 3 during development otherwise you will wait for a long time
    # For benchmarking you must set it to a large number, e.g., 100
    #Note that file is opened in append mode, previous results will be kept in the file
    resultfile = open("results.csv", "w")  # Measurement results are collated in this file for you to plot later on
    resultfile.write("NodeCount,SimCnt,totalCompiletime,KeyGenerationTime,EncryptionTime,ExecutionTime,DecryptionTime,ReferenceExecutionTime,Mse\n")
    resultfile.close()
    
    print("Simulation campaing started:")

    for nc in range(8,50,4): # Node counts for experimenting various graph sizes
        n = nc

        resultfile = open("results.csv", "a") 
        for i in range(simcnt):
            #Call the simulator
            totalCompiletime, totalKeygenerationtime, totalEncryptiontime, totalExecutiontime, totalDecryptiontime, totalReferenceexecutiontime, totalMse = simulate(n)
            res = str(n) + "," + str(i) + "," + str(totalCompiletime) + "," + str(totalKeygenerationtime) + "," +  str(totalEncryptiontime) + "," +  str(totalExecutiontime) + "," +  str(totalDecryptiontime) + "," +  str(totalReferenceexecutiontime) + "," +  str(totalMse) + "\n"
            resultfile.write(res)
            
        resultfile.close()

    #plotResults()

    
