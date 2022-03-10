# iris_classifier.py

import pennylane as qml
from pennylane import numpy as np
from pennylane.optimize import NesterovMomentumOptimizer

from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

import common as com

np.random.seed(123) # Set seed for reproducibility

# Collect this in a class
class Data:

	def __init__(self, X, Y):
		self.X = X
		self.Y = Y

# The layer for the circuit
def layer_ex1(weights):
	n = len(weights)

	# Adds rotation matrices
	for i, row in enumerate(weights):
		qml.Rot(row[0], row[1], row[2], wires = i)

	# Adds controlled NOT matrices
	for i in range(n):
		qml.CNOT(wires = [i, (i + 1) % n])

def layer_ex2(weights):
    n = len(weights)

    # Adds rotation matrices and controlled NOT matrices
    for i, row in enumerate(weights):
        qml.Rot(row[0], row[1], row[2], wires = i)
        qml.CNOT(wires = [i, (i + 1) % n])

# Looking at equation 8 in https://arxiv.org/pdf/quant-ph/0407010.pdf
# With n = number of qubits, and k = 1, 2, ..., n
def get_angles(x):

    # Number of qubits needed to encode x
    # Should be equal to n_qubits
    # Should be a power of two
    n = np.int64(np.ceil(np.log2(len(x))))

    # Matrix for holding our angles
    beta = np.zeros(shape = (2 ** (n - 1), n))

    for k in range(n):
        for j in range(2 ** (n - k - 1)):
            # Compute the numerator inside the arcsin
            num = np.sqrt(sum(
                np.abs(x[(2 * j + 1) * 2 ** k + l]) ** 2
                    for l in range(2 ** k)
            ))
            # Compute the denomenator inside the arcsin
            den = np.sqrt(sum(
                np.abs(x[j * 2 ** (k + 1) + l]) ** 2
                    for l in range(2 ** (k + 1))
            ))
            beta[j, k] = 2 * np.arcsin(num / den)

    #return beta
    return np.array([
        beta[0, 1],
        -beta[1, 1] / 2,
        beta[1, 1] / 2,
        -beta[0, 0] / 2,
        beta[0, 0] / 2
    ])
 
def stateprep_ex(angles):

	qml.RY(angles[0], wires = 0)

	# Should be the same as n_qubits
	n = len(angles) // 2

	for i in range(n):
		for j in range(n):
			qml.CNOT(wires = [0, 1])
			qml.RY(angles[2 * i + j + 1], wires = 1)

		qml.PauliX(wires = 0)

def stateprep_amplitude(features):
    wires = np.int64(np.ceil(np.log2(len(features))))
    qml.AmplitudeEmbedding(features = features, wires = range(wires), normalize = True)

# The circuit function, allows variable statepreparation and layer functions
def circuit_fun(weights, features, stateprep_fun, layer_fun):

	stateprep_fun(features)

	for weight in weights:
		layer_fun(weight)

	return qml.expval(qml.PauliZ(0))

def variational_classifier_fun(weights, features, bias, circuit_fun):
	return circuit_fun(weights, features) + bias

def cost_fun(weights, bias, features, labels, variational_classifier_fun):
	preds = [variational_classifier_fun(weights, feature, bias) for feature in features]
	return com.square_loss(labels, preds)

def optimise(n_iter, weights, bias, data, data_train, data_val, circuit):
	opt = NesterovMomentumOptimizer(stepsize = 0.01) # Performs much better than GradientDescentOptimizer
	# opt = AdamOptimizer(stepsize = 0.01) # To be tried, was mentioned
	batch_size = 5 # This might be something which can be adjusted
	
	# Variational classifier function used by pennylane
	def variational_classifier(weights, features, bias):
		return variational_classifier_fun(weights, features, bias, circuit)

	# Cost function used by pennylane
	def cost(weights, bias, features, labels):
		return cost_fun(weights, bias, features, labels, variational_classifier)

	# Number of training points, used when choosing batch indexes
	n_train = len(data_train.Y)

	for i in range(n_iter):

		# Update the weights by one optimiser step
		batch_index = np.random.randint(0, high = n_train, size = (batch_size, ))
		X_train_batch = data_train.X[batch_index]
		Y_train_batch = data_train.Y[batch_index]
		weights, bias, _, _ = opt.step(cost, weights, bias, X_train_batch, Y_train_batch)

		# Compute predictions on train and test set
		predictions_train = [np.sign(variational_classifier(weights, x, bias)) for x in data_train.X]
		predictions_val = [np.sign(variational_classifier(weights, x, bias)) for x in data_val.X]

		# Compute accuracy on train and test set
		accuracy_train = com.accuracy(data_train.Y, predictions_train)
		accuracy_val = com.accuracy(data_val.Y, predictions_val)

		print(
			'Iteration: {:5d} | Cost: {:0.7f} | Accuracy train: {:0.7f} | Accuracy validation: {:0.7f} '
			''.format(i + 1, cost(weights, bias, data.X, data.Y), accuracy_train, accuracy_val)
		)

# Split a data object into training and validation data
# p is the proportion of the data which should be used for training
def split_data(data, p):

	X_train, X_val, Y_train, Y_val = train_test_split(data.X, data.Y, train_size = p)

	return Data(X_train, Y_train), Data(X_val, Y_val)

def run_variational_classifier(n_qubits, n_layers, data, stateprep_fun, layer_fun):

	# The device and qnode used by pennylane
	device = qml.device("default.qubit", wires = n_qubits)

	# Circuit function used by pennylane
	@qml.qnode(device)
	def circuit(weights, x):
		return circuit_fun(weights, x, stateprep_fun, layer_fun)

	# The proportion of the data which should be use for training
	p = 0.7

	data_train, data_val = split_data(data, p)

	n_iter = 60 # Number of iterations, should be changed to a tolerance based process instead

	weights = 0.01 * np.random.randn(n_layers , n_qubits, 3, requires_grad = True) # Initial value for the weights
	bias = np.array(0.0, requires_grad = True) # Initial value for the bias

	optimise(n_iter, weights, bias, data, data_train, data_val, circuit)

# Load the iris data set from sklearn into a data object
def load_data():

	# Load the data set
    data = load_iris()

    X = data['data']
    Y = data['target']

    # We will only look at two types, -1 and 1
    # In Y, elements are of three types 0, 1, and 2.
    # We simply cutoff the 2:s for now
    # The array is sorted so we can easily find first occurence of a 2 with binary search
    cutoff = np.searchsorted(Y, 2)

    # Now simply remove the x:s and y:s corresponding to the 2:s
    X = X[: cutoff]
    Y = Y[: cutoff]

    # Scale and translate Y from 0 and 1 to -1 and 1
    Y = 2 * Y - 1
    Y = np.array(Y) # PennyLane numpy differ from normal numpy. Converts np.ndarray to pennylane.np.tensor.tensor

    # Normalise each row in X
    X_norm = np.linalg.norm(X, axis = 1).reshape(100, 1) # Because X is ndarray X_norm is a tensor 
    X = X / X_norm

    # Get the angle
    #X = np.array([get_angles(x) for x in X], requires_grad = False)

    return Data(X, Y)

def main():

	n_qubits = 2
	n_layers = 6

	# Can be any function that takes an input vector and encodes it
	stateprep_fun = stateprep_amplitude

	# Can be any function which takes in a matrix of weights and creates a layer
	layer_fun = layer_ex1

	# Load the iris data
	data = load_data()

	run_variational_classifier(
		n_qubits,
		n_layers,
		data,
		stateprep_fun,
		layer_fun
	)

if __name__ == '__main__':
	main()
