# © 2022 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.
import numpy as np
import scipy.stats


def generate_density_estimation(performance: np.ndarray, minimum: int, maximum: int, steps: int = 5000):
    xs = []
    ys = []
    n = len(performance)
    h = _estimate_bandwidth(performance)
    coefficient = 1. / (h * np.sqrt(2 * np.pi))
    step_size = (maximum - minimum) / float(steps)
    for i in range(steps + 1):
        x = minimum + i * step_size
        xs.append(x)
        y = np.sum(np.exp(-0.5 * ((x - performance) / h) ** 2) * coefficient) / n
        ys.append(y)
    return xs, ys


def _estimate_bandwidth(performance: np.ndarray):
    s = np.std(performance)
    iqr = scipy.stats.iqr(performance)
    coefficient = len(performance) ** (-1. / 5.)
    return 0.9 * min(s, iqr / 1.34) * coefficient
