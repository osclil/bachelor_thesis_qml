from distutils.util import execute
from hmac import trans_36
from unicodedata import digit
from sklearn import datasets
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, StandardScaler, minmax_scale
from sklearn.svm import SVC
from sklearn.decomposition import PCA
import numpy as np
from qiskit.circuit.library import *
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister, Aer, execute
from qiskit.tools.visualization import circuit_drawer
from urllib3 import encode_multipart_formdata
from qiskit_machine_learning.kernels import QuantumKernel

# Test123123

digits = datasets.load_digits(n_class=2)
iris = datasets.load_iris()

print("123123")

X = iris.data#[:100]
Y = iris.target#[:100]

x_train, x_test, y_train, y_test = train_test_split(X, Y, test_size=0.3, random_state=10)

# Data manipulation for the digits dataset

# Split the dataset
sample_train, sample_test, label_train, label_test = train_test_split(
    digits.data, digits.target, test_size=0.2, random_state=25)

# Reduce dimensions
n_dim = 4
pca = PCA(n_components=n_dim).fit(sample_train)
sample_train = pca.transform(sample_train)
sample_test = pca.transform(sample_test)

# Normalise
std_scale = StandardScaler().fit(sample_train)
sample_train = std_scale.transform(sample_train)
sample_test = std_scale.transform(sample_test)

# Scale
samples = np.append(sample_train, sample_test, axis=0)
minmax_scale = MinMaxScaler((-1, 1)).fit(samples)
sample_train = minmax_scale.transform(sample_train)
sample_test = minmax_scale.transform(sample_test)

zz_map = ZZFeatureMap(feature_dimension=4, reps = 2, entanglement="linear", insert_barriers=True)
zz_kernel = QuantumKernel(feature_map=zz_map, quantum_instance=Aer.get_backend('statevector_simulator'))
zz_circuit = zz_kernel.construct_circuit(x_train[0], x_train[1])
#print(zz_circuit)

backend = Aer.get_backend('qasm_simulator')
job = execute(zz_circuit, backend, shots = 8192, seed_simulator=1024, seed_transpiler=1024)
counts = job.result().get_counts(zz_circuit)

matrix_train = zz_kernel.evaluate(x_vec=x_train)
matrix_test = zz_kernel.evaluate(x_vec=x_test, y_vec=x_train)

zzpc_svc = SVC(kernel='precomputed')
zzpc_svc.fit(matrix_train, y_train)
zzpc_score = zzpc_svc.score(matrix_test, y_test)

print(zzpc_score)
