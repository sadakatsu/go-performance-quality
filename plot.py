# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.
from typing import Tuple

import matplotlib.font_manager
import matplotlib.pyplot as plt
import numpy as np

from fontTools.ttLib import TTFont
from matplotlib.ticker import MultipleLocator

from common import get_filename_core, ImageData
from load_statistics import get_expected_result, load_performances, get_worst_moves
from matplotlib import rcParams

from kde import generate_density_estimation
from histogram import generate_histogram


def plot_distributions(
    plots_directory: str,
    analysis_filename: str,
    black_name: str,
    white_name: str,
    target_width: int
) -> Tuple[ImageData, ImageData]:
    # TODO: Refactor this code into two branches: one for KDE, one for expected result.
    _set_matplotlib_fonts(analysis_filename)

    filename_core = get_filename_core(analysis_filename)
    distribution_filename = f'{plots_directory}/{filename_core}__kde.png'
    expected_result_filename = f'{plots_directory}/{filename_core}__er.png'

    width = target_width // 2
    height = round(width * 3. / 4)
    size = (width, height)

    performances = load_performances(analysis_filename, use_rounded=False)
    minimum = _get_safe_minimum(performances)
    maximum = _get_safe_maximum(performances)

    black_performance = _get_performance(performances, 'B')
    white_performance = _get_performance(performances, 'W')

    bin_width = 0.25
    black_histogram_xs, black_histogram_ys = generate_histogram(black_performance, minimum, maximum, bin_width)
    white_histogram_xs, white_histogram_ys = generate_histogram(white_performance, minimum, maximum, bin_width)

    black_pdf_xs, black_pdf_ys = generate_density_estimation(black_performance, minimum, maximum)
    white_pdf_xs, white_pdf_ys = generate_density_estimation(white_performance, minimum, maximum)

    plt.close('all')
    figure, axis_histogram = plt.subplots()
    axis_histogram.set_title('Mistake Distribution')
    axis_histogram.set_xlabel('better   <<   Mistake Cost in Points   >>   worse')
    axis_histogram.set_ylabel('Proportion of Moves')
    axis_histogram.set_xlim(minimum, maximum)
    axis_histogram.set_ylim(0., 1.)
    axis_histogram.grid(True, linewidth=0.5, zorder=0)

    bar_width = bin_width * 2. / 5
    axis_histogram.bar(
        black_histogram_xs,
        black_histogram_ys,
        align='edge',
        width=-bar_width,
        label=f'{black_name} (Black)',
        zorder=3
    )
    axis_histogram.bar(
        white_histogram_xs,
        white_histogram_ys,
        align='edge',
        width=bar_width,
        label=f'{white_name} (White)',
        zorder=3
    )
    axis_histogram.legend(loc='upper right')

    axis_kde = axis_histogram.twinx()
    axis_kde.set_ylabel('Estimated PDF')
    axis_kde.plot(black_pdf_xs, black_pdf_ys, linewidth=0.75)
    axis_kde.plot(white_pdf_xs, white_pdf_ys, linewidth=0.75)
    axis_kde.set_ylim(bottom=0.)

    plt.tight_layout()
    figure.set_size_inches(width / 100, height / 100)
    plt.savefig(distribution_filename, format='png', dpi=100)

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
    figure.set_size_inches(width / 100, height / 100)
    plt.savefig(expected_result_filename, format='png')

    return (
        ImageData(expected_result_filename, width, height),
        ImageData(distribution_filename, width, height),
    )


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
