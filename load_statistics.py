import numpy as np
import pandas as pd
import re
import sys


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
    matcher = re.search(r'^(?:[^/\\]*[/\\])*(?P<date>\d{4,}-\d{2}-\d{2})_(?P<name>[^_]+).csv$', analysis_filename)
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
        result = player_slice['Before'].to_numpy() - player_slice['After'].to_numpy()

    return result
