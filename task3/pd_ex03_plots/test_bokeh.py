import io
import urllib.request

import numpy as np
from bokeh.plotting import figure, show

_MNIST_NPZ = (
    "https://storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz"
)


def _load_mnist_train() -> tuple[np.ndarray, np.ndarray]:
    with urllib.request.urlopen(_MNIST_NPZ) as r:
        raw = r.read()
    with np.load(io.BytesIO(raw)) as data:
        return data["x_train"], data["y_train"]


x_train, train_labels = _load_mnist_train()
total_classes = 3
ind = np.where(train_labels < total_classes)
x_train, train_labels = x_train[ind], train_labels[ind]
total_examples, img_length, img_width = x_train.shape
print("Training data has ", total_examples, "images")
print("Each image is of size ", img_length, "x", img_width)

x = np.reshape(x_train, (x_train.shape[0], -1)).astype(np.float32)
eigenvalues, eigenvectors = np.linalg.eigh(x.T @ x)
print("3 largest eigenvalues: ", eigenvalues[-3:])
x_pca = x @ eigenvectors

colormap = {0: "red", 1: "green", 2: "blue"}
my_scatter = figure(
    title="First Two Dimensions of Projected Data After Applying PCA",
    x_axis_label="Dimension 1",
    y_axis_label="Dimension 2",
)
for digit in [0, 1, 2]:
    selection = x_pca[train_labels == digit]
    my_scatter.scatter(
        selection[:, -1],
        selection[:, -2],
        color=colormap[digit],
        size=5,
        alpha=0.5,
        legend_label="Digit " + str(digit),
    )
my_scatter.legend.click_policy = "hide"
show(my_scatter)
