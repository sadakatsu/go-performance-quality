# © 2022 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.
import numpy as np


def generate_histogram(performance: np.ndarray, minimum: int, maximum: int, bin_width: float = 0.1, normalize=True):
    half_width = bin_width * 0.5
    n = len(performance)
    xs = []

    x = minimum
    i = -1
    while x < maximum:
        i += 1
        x = minimum + i * bin_width
        xs.append(x)

    xs = np.array(xs)

    ys = np.zeros(len(xs))
    for value in performance:
        # I don't like this nested loop.  I am using it while I try to fix how the histogram is being generated.  It
        # might stay here because I am trying to move on with other things  >_<
        for i, candidate in enumerate(xs):
            difference = value - candidate
            if -half_width <= difference < half_width:
                index = i
                break
        ys[index] += 1

    if normalize:
        ys /= n

    return xs, ys
