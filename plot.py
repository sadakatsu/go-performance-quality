# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.

import matplotlib.font_manager
import matplotlib.pyplot as plt
import numpy as np
import re
import scipy.stats

from fontTools.ttLib import TTFont
from load_statistics import load_performances
from matplotlib import rcParams


def plot_distributions(plots_directory: str, analysis_filename: str, black_name: str, white_name: str):
    _set_matplotlib_fonts(analysis_filename)

    filename_core = _get_filename_core(analysis_filename)
    title = filename_core.replace('__', '\n')

    performances = load_performances(analysis_filename, use_rounded=False)
    minimum = _get_safe_minimum(performances)
    maximum = _get_safe_maximum(performances)

    black_performance = _get_performance(performances, 'B')
    white_performance = _get_performance(performances, 'W')

    black_xs, black_ys = _generate_density_estimation(black_performance, minimum, maximum)
    white_xs, white_ys = _generate_density_estimation(white_performance, minimum, maximum)

    plt.title(title)
    plt.xlabel('Mistake Cost in Points')
    plt.ylabel('Proportion of Moves')
    plt.xlim(minimum, maximum)
    plt.ylim(0., 1.)
    plt.plot(black_xs, black_ys, label=f'Black ({black_name})')
    plt.plot(white_xs, white_ys, label=f'White ({white_name})')
    plt.legend(loc='upper right')
    plt.savefig(f'{plots_directory}/{filename_core}.png', format='png')


def _set_matplotlib_fonts(analysis_filename: str):
    needed = set(analysis_filename)

    default_font = matplotlib.font_manager.findfont('DejaVu Sans')
    default_ttf = TTFont(default_font, fontNumber=0)
    missing = {x for x in needed if not _char_in_font(x, default_ttf)}

    if missing:
        candidates = []
        for f in matplotlib.font_manager.fontManager.ttflist:
            name = f.name
            ttf = TTFont(f.fname, fontNumber=0)
            covered = {x for x in missing if _char_in_font(x, ttf)}
            if covered:
                candidate = name, covered
                candidates.append(candidate)

        ordered = sorted(candidates, key=lambda x: len(x[1]), reverse=True)
        name, covered = ordered[0]
        rcParams['font.family'] = 'serif'
        rcParams['font.serif'] = [name]
    else:
        rcParams['font.family'] = 'sans-serif'
        rcParams['font.sans-serif'] = ['DejaVu Sans']


def _char_in_font(character, font):
    # found at https://jdhao.github.io/2018/04/08/matplotlib-unicode-character/
    for cmap in font['cmap'].tables:
        if cmap.isUnicode():
            if ord(character) in cmap.cmap:
                return True
    return False


def _get_filename_core(analysis_filename: str):
    return re.match(r'^(?:[^\\/]*[\\/])*(.*)\.csv$', analysis_filename).group(1)


def _get_performance(performances, color: str):
    return [x[2] for x in performances if x[1] == color][0]


def _get_safe_minimum(performances):
    a = np.min(performances[0][2])
    b = np.min(performances[1][2])
    return np.floor(min(a, b))


def _get_safe_maximum(performances):
    a = np.max(performances[0][2])
    b = np.max(performances[1][2])
    return np.ceil(max(a, b))


def _generate_density_estimation(performance: np.ndarray, minimum: int, maximum: int, steps: int = 5000):
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
