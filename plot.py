# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.

import matplotlib.font_manager
import matplotlib.pyplot as plt
import numpy as np
import re
import scipy.stats

from fontTools.ttLib import TTFont
from matplotlib.ticker import MultipleLocator

from load_statistics import get_expected_result, load_performances, get_worst_moves
from matplotlib import rcParams


def plot_distributions(plots_directory: str, analysis_filename: str, black_name: str, white_name: str):
    # TODO: Refactor this code into two branches: one for KDE, one for expected result.
    _set_matplotlib_fonts(analysis_filename)

    filename_core = _get_filename_core(analysis_filename)

    performances = load_performances(analysis_filename, use_rounded=False)
    minimum = _get_safe_minimum(performances)
    maximum = _get_safe_maximum(performances)

    black_performance = _get_performance(performances, 'B')
    white_performance = _get_performance(performances, 'W')

    black_xs, black_ys = _generate_density_estimation(black_performance, minimum, maximum)
    white_xs, white_ys = _generate_density_estimation(white_performance, minimum, maximum)

    plt.close('all')
    plt.figure(1)
    plt.title('Estimated Mistake Distribution')
    plt.xlabel('Mistake Cost in Points')
    plt.ylabel('Proportion of Moves')
    plt.xlim(minimum, maximum)
    plt.ylim(0., 1.)
    plt.plot(black_xs, black_ys, label=f'Black ({black_name})')
    plt.plot(white_xs, white_ys, label=f'White ({white_name})')
    plt.legend(loc='upper right')
    plt.tight_layout()
    plt.savefig(f'{plots_directory}/{filename_core}__kde.png', format='png')

    expected_result = get_expected_result(analysis_filename)
    move_count = len(expected_result)
    move_indices = [i + 1 for i in range(move_count)]
    mistake_indices, worst_mistakes = get_worst_moves(analysis_filename)
    mistake_ceiling = int(np.ceil(np.max(np.abs(worst_mistakes)) + 1))

    plt.close('all')
    figure = plt.figure(2)
    figure.suptitle('Expected Result by Move and Worst Mistakes')

    expected_result_plot = plt.subplot2grid((5, 1), (1, 0), rowspan=3)
    expected_result_plot.grid()
    expected_result_plot.set_ylabel('Expected Result')
    expected_result_plot.plot(move_indices, expected_result, linewidth=0.5)
    expected_result_plot.set_xlim(-1, move_count + 1)

    black_worst_plot = plt.subplot2grid((5, 1), (0, 0))
    black_worst_plot.grid(zorder=0)
    black_worst_plot.xaxis.set_ticklabels([])
    black_worst_plot.yaxis.set_major_locator(MultipleLocator(5))
    black_worst_plot.yaxis.set_major_formatter(lambda x, _: int(abs(x)))
    black_worst_plot.set_xlim(-1, move_count + 1)
    black_worst_plot.set_ylim(-mistake_ceiling, 0)
    black_worst_plot.set_ylabel('Black Worst')
    black_worst_plot.bar(mistake_indices, -worst_mistakes, color='red', width=1, zorder=2)

    white_worst_plot = plt.subplot2grid((5, 1), (4, 0))
    white_worst_plot.grid(zorder=0)
    white_worst_plot.xaxis.set_ticklabels([])
    white_worst_plot.yaxis.set_major_locator(MultipleLocator(5))
    white_worst_plot.set_ylim(0, mistake_ceiling)
    white_worst_plot.set_xlim(-1, move_count + 1)
    white_worst_plot.set_ylabel('White Worst')
    white_worst_plot.bar(mistake_indices, -worst_mistakes, color='red', width=1, zorder=2)

    for index, magnitude in zip(mistake_indices, worst_mistakes):
        label = index % 100 if index // 100 != index / 100 else index
        if magnitude > 0:
            black_worst_plot.annotate(
                label,
                (index, -magnitude),
                fontsize=6,
                ha='center',
                textcoords='offset points',
                xytext=(0, -7)
            )
        else:
            white_worst_plot.annotate(
                label,
                (index, -magnitude),
                fontsize=6,
                ha='center',
                textcoords='offset points',
                xytext=(0, 1)
            )

    plt.tight_layout()
    plt.savefig(f'{plots_directory}/{filename_core}__er.png', format='png')


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
