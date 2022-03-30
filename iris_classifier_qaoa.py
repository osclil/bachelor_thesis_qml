# iris_classifier.py

import pennylane as qml
from pennylane import numpy as np
import pennylane.optimize as opt

from sklearn.datasets import load_iris, load_breast_cancer, fetch_covtype
from sklearn.model_selection import train_test_split

import common as com

import json

np.random.seed(123) # Set seed for reproducibility

# Collect this in a class
class Data:

	def __init__(self, X, Y):
		self.X = X
		self.Y = Y

def circuit_QAOA(features, weights):
	wires = len(features)
	qml.QAOAEmbedding(features = features, weights = weights, wires = range(wires))
	return qml.expval(qml.PauliZ(0))

def variational_classifier_fun(features, weights, bias, circuit_fun):
	return circuit_fun(features, weights) + bias

def cost_fun(weights, bias, features, labels, variational_classifier_fun):
	preds = [variational_classifier_fun(weights, feature, bias) for feature in features]
	return com.square_loss(labels, preds)

def optimise(n_iter, weights, bias, data, data_train, data_val, circuit):
	optimiser = opt.NesterovMomentumOptimizer(stepsize = 0.01) # Performs much better than GradientDescentOptimizer
	#optimiser = opt.AdamOptimizer(stepsize = 0.01) # To be tried, was mentioned
	#optimiser = opt.GradientDescentOptimizer(stepsize = 0.01)
	batch_size = 5 # This might be something which can be adjusted

	costs = []
	acc_train = []
	acc_val = []

	# Variational classifier function used by pennylane
	def variational_classifier(weights, features, bias):
		return variational_classifier_fun(features, weights, bias, circuit)

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
		weights, bias, _, _ = optimiser.step(cost, weights, bias, X_train_batch, Y_train_batch)
		# Compute predictions on train and test set
		predictions_train = [np.sign(variational_classifier(weights, x, bias)) for x in data_train.X]
		predictions_val = [np.sign(variational_classifier(weights, x, bias)) for x in data_val.X]

		# Compute accuracy on train and test set
		accuracy_train = com.accuracy(data_train.Y, predictions_train)
		accuracy_val = com.accuracy(data_val.Y, predictions_val)

		cost_ = cost(weights, bias, data.X, data.Y)

		print(
			'Iteration: {:5d} | Cost: {:0.7f} | Accuracy train: {:0.7f} | Accuracy validation: {:0.7f} '
			''.format(i + 1, cost_, accuracy_train, accuracy_val)
		)

		costs.append(float(cost_))
		acc_train.append(float(accuracy_train))
		acc_val.append(float(accuracy_val))

	doc = {
		'costs': costs,
		'acc_train': acc_train,
		'acc_val': acc_val
	}

	with open('data/test.json', 'w') as f:
		json.dump(doc, f)

# Split a data object into training and validation data
# p is the proportion of the data which should be used for training
def split_data(data, p):

	X_train, X_val, Y_train, Y_val = train_test_split(data.X, data.Y, train_size = p)

	return Data(X_train, Y_train), Data(X_val, Y_val)

def run_variational_classifier(n_qubits, n_layers, data, circuit_fun):

	# The device and qnode used by pennylane
	device = qml.device("default.qubit", wires = n_qubits)

	# Circuit function used by pennylane
	@qml.qnode(device)
	def circuit(features, weights):
		return circuit_fun(features, weights)

	# The proportion of the data which should be use for training
	p = 0.7

	data_train, data_val = split_data(data, p)

	n_iter = 200 # Number of iterations, should be changed to a tolerance based process instead

	weights = 0.01 * np.random.randn(n_layers , 2 * n_qubits, requires_grad = True) # Initial value for the weights
	bias = np.array(0.0, requires_grad = True) # Initial value for the bias

	optimise(n_iter, weights, bias, data, data_train, data_val, circuit)

# Load the iris data set from sklearn into a data object
def load_data_iris():

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

	# PennyLane numpy differ from normal numpy.
	# Converts np.ndarray to pennylane.np.tensor.tensor
	Y = np.array(Y)
	X = np.array([np.array(x) for x in X], requires_grad = False)

	return Data(X, Y)

def load_data_cancer():

	# Load the data set
	data = load_breast_cancer()

	X = data['data']
	Y = data['target']

	# Scale and translate Y from 0 and 1 to -1 and 1
	Y = 2 * Y - 1

	# PennyLane numpy differ from normal numpy.
	# Converts np.ndarray to pennylane.np.tensor.tensor
	Y = np.array(Y)
	X = np.array([np.array(x) for x in X], requires_grad = False)

	return Data(X, Y)

def load_data_forest():

	# Load the data set
	data = fetch_covtype()

	X_raw = data['data']
	Y_raw = data['target']

	Y = []
	X = []

	# It turns out this will yield a dataset of 495 141 points
	# We limit the size to the first 500 for now
	# Might be replaced with a random sample instead

	# In the forest data elements can be of type 1 to 7
	# We only log at type 1 and type 2
	cnt = 0
	for x, y in zip(X_raw, Y_raw):
		if y < 3:
			X.append(np.array(x))
			Y.append(y)
			# Not 
			cnt = cnt + 1
			if cnt == 500:
				break

	# Convert to numpy array
	Y = np.array(Y)
	X = np.array(X)

	# Scale and translate Y from 1 and 2 to -1 and 1
	Y = 2 * Y - 3

	return Data(X, Y)

def main():

	n_qubits = 4
	n_layers = 6

	# Can be any function that takes an input of features and weights
	circuit_fun = circuit_QAOA


	# Load the iris data
	data = load_data_iris()

	run_variational_classifier(
		n_qubits,
		n_layers,
		data,
		circuit_fun,
	)

if __name__ == '__main__':
	main()