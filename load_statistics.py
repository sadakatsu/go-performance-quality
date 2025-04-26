# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.
from typing import List, Tuple

import numpy as np
import pandas as pd
import re
import sys


def load_performances_new(analysis_filename: str) -> dict:
    loaded = load(analysis_filename)
    if not loaded:
        print(f'Failed to load {analysis_filename}')
        sys.exit(4)
    date, game_name, dataframe = loaded

    black_moves = dataframe[dataframe['Player'] == 'B']
    white_moves = dataframe[dataframe['Player'] == 'W']

    return {
        'Game': {
            'actual': dataframe['Loss'].to_numpy(),
            'expected': dataframe['Expected Loss'].to_numpy(),
        },
        'B': {
            'actual': black_moves['Loss'].to_numpy(),
            'expected': black_moves['Expected Loss'].to_numpy(),
        },
        'W': {
            'actual': white_moves['Loss'].to_numpy(),
            'expected': white_moves['Expected Loss'].to_numpy(),
        },
    }


def load_performances(analysis_filename, use_rounded=True, minimum_moves=21):
    performances = []

    def add_performance(player, mistakes):
        nonlocal performances
        mean = np.mean(mistakes)
        standard_deviation = np.std(mistakes)
        performances.append((game_name, player, mistakes, mean, standard_deviation))

    loaded = load(analysis_filename)
    if not loaded:
        print(f'Failed to load {analysis_filename}')
        sys.exit(4)
    date, game_name, dataframe = loaded

    black_name = 'B'
    black_mistakes = get_mistakes(dataframe, 'B', use_rounded=use_rounded)
    if len(black_mistakes) >= minimum_moves:
        add_performance(black_name, black_mistakes)
    else:
        print(f'Rejected ({game_name}, {black_name}) for being too short.')

    white_name = 'W'
    white_mistakes = get_mistakes(dataframe, 'W', use_rounded=use_rounded)
    if len(white_mistakes) >= minimum_moves:
        add_performance(white_name, white_mistakes)
    else:
        print(f'Rejected ({game_name}, {white_name}) for being too short.')

    return performances


def load(analysis_filename):
    matcher = re.search(r'^(?:[^/\\]*[/\\])*(?P<date>\d{4,}-\d{2}-\d{2})__.*__(?P<name>.+).csv$', analysis_filename)
    if not matcher:
        return None
    return (
        matcher.group('date'),
        matcher.group('name'),
        pd.read_csv(analysis_filename)
    )


def get_mistakes(dataframe, player, use_rounded=True):
    player_slice = dataframe[dataframe['Player'] == player]
    if use_rounded:
        result = player_slice['Mistake'].to_numpy()
    else:
        result = player_slice['Prior Lead'].to_numpy() - player_slice['Posterior Lead'].to_numpy()

    return result


def get_expected_result(analysis_filename: str) -> List[float]:
    _1, _2, dataframe = load(analysis_filename)
    subset = zip(dataframe['Player'], dataframe['Posterior Lead'])
    return [np.round(x if p == 'B' else -x, 1) for p, x in subset]


def get_worst_moves(analysis_filename: str) -> Tuple[List[int], np.array]:
    _1, _2, dataframe = load(analysis_filename)

    black_mistakes = np.array([x if p == 'B' else np.NaN for p, x in zip(dataframe['Player'], dataframe['Loss'])])
    worst_black_mistake_indices = np.sort((-black_mistakes).argsort()[:10])
    worst_black_mistakes = np.array([black_mistakes[i] for i in worst_black_mistake_indices])

    white_mistakes = np.array([-x if p == 'W' else np.NaN for p, x in zip(dataframe['Player'], dataframe['Loss'])])
    worst_white_mistake_indices = np.sort(white_mistakes.argsort()[:10])
    worst_white_mistakes = np.array([white_mistakes[i] for i in worst_white_mistake_indices])

    # indices are one off move numbers
    indices = np.concatenate((worst_black_mistake_indices, worst_white_mistake_indices)) + 1
    worst = np.concatenate((worst_black_mistakes, worst_white_mistakes))

    return indices, worst
