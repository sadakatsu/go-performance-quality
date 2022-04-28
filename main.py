# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.

import csv
from typing import Optional, Callable

import dateparser
import numpy as np
import os.path
import json
import re
import sys
import time
import yaml

from glob import glob

from infographic import generate_infographic
from katago import KataGo, LineType
from kifu import print_kifu
from load_statistics import load_performances
from parse import parse_sgf_contents, transform_sgf_to_command
from plot import plot_distributions
from render import render_table


katago: Optional[KataGo] = None
get_katago: Optional[Callable[[], KataGo]] = None


def prep_katago(katago_configuration: dict):
    global get_katago, katago

    def created():
        global katago

        if not katago:
            print('Starting KataGo...')
            katago = KataGo(
                katago_configuration['executable'],
                katago_configuration['configuration'],
                katago_configuration['model'],
                analysis_threads=katago_configuration['analysisThreads'],
                search_threads=katago_configuration['searchThreads']
            )
            while not katago.ready:
                time.sleep(0.001)
            print('KataGo started.')

        return katago

    get_katago = created


def run(sgf_filename):
    global katago

    configuration = load_configuration()

    prep_katago(configuration['katago'])

    parameters, transformation = load_parameters(configuration['transformation_parameters'])

    game = load_sgf(sgf_filename)
    root = game[0]
    black_name = root['PB']
    white_name = root['PW']
    result = root['RE']
    if result.startswith('B+'):
        winner = 'B'
    elif result.startswith('W+'):
        winner = 'W'
    else:
        winner = None

    analysis_filename = get_or_create_analysis_file(
        sgf_filename,
        game,
        configuration['analyses_directory'],
        configuration['katago']
    )
    original_performances = load_performances(analysis_filename)
    performance_matrix = transform_to_performance_matrix(original_performances)
    scaled = scale(performance_matrix, parameters)
    transformed = scaled @ transformation
    summary = summarize(analysis_filename)

    black_quality = f'{transformed[0, 0]:+0.3f}'
    white_quality = f'{transformed[1, 0]:+0.3f}'

    performance_table = render_table(
        configuration['renders_directory'],
        analysis_filename,
        black_name,
        white_name,
        winner,
        black_quality,
        white_quality,
        summary['B'],
        summary['W']
    )

    kifu = print_kifu(
        configuration['kifu_directory'],
        analysis_filename,
        game,
        performance_table.height
    )

    target_width = kifu.width + performance_table.width

    expected_result, distribution = plot_distributions(
        configuration['plots_directory'],
        analysis_filename,
        black_name,
        white_name,
        target_width
    )

    infographic = generate_infographic(
        configuration,
        analysis_filename,
        game,
        kifu,
        performance_table,
        expected_result,
        distribution
    )

    print('\nPlayer, Moves, Mistakes, p(Mistake), Loss Total, Loss Mean, Loss Std. Dev., Quality')
    for player in ['B', 'W']:
        full_player = 'Black' if player == 'B' else 'White'
        player_summary = summary[player]
        index = next((i for i, x in enumerate(original_performances) if x[1] == player), None)
        quality = transformed[index, 0]
        print(
            full_player,
            player_summary['moves'],
            player_summary['mistakes'],
            print_neat_float(player_summary['p(mistake)']),
            player_summary['loss_total'],
            print_neat_float(player_summary['loss_mean']),
            print_neat_float(player_summary['loss_std_dev']),
            f'{quality:+0.3f}',
            sep=', '
        )

    print(f'\nYou can find your infographic at {infographic.filename} .')

    if katago:
        katago.kill()

def load_configuration():
    with open('configuration/application.yaml') as infile:
        configuration = yaml.safe_load(infile)
    test_configuration_value(configuration, 'analyses_directory', os.path.isdir)
    test_configuration_value(configuration, 'transformation_parameters', os.path.isfile)
    return configuration


def test_configuration_value(configuration, key, test):
    if not (key in configuration and test(configuration[key])):
        print(f'Check configuration/application.yaml\'s {key} value.')
        sys.exit(1)


def load_parameters(filename):
    with open(filename, 'rb') as infile:
        configuration = np.load(infile, allow_pickle=True)
        return configuration['parameters'].item(), configuration['transformation']


def get_or_create_analysis_file(sgf_filename, game, analyses_directory, katago_configuration):
    base_name = get_base_filename(sgf_filename)
    analysis_filename = find_existing_analysis(base_name, analyses_directory)
    if analysis_filename:
        print(f'Found {analysis_filename} .')
    else:
        analysis_filename = perform_analysis(sgf_filename, game, base_name, analyses_directory, katago_configuration)
    return analysis_filename


def get_base_filename(file):
    filename = os.path.basename(file)
    index = filename.rfind('.')
    if index != -1:
        filename = filename[:index]
    return re.sub(r'\s+', '_', filename)


def find_existing_analysis(base_name, analyses_directory):
    if not analyses_directory.endswith('/'):
        analyses_directory += '/'
    needle = f'{analyses_directory}*_{base_name}.csv'
    haystack = [x for x in glob(needle)]
    return haystack[0] if haystack else None


def perform_analysis(sgf_filename, game, base_name, analyses_directory, katago_configuration):
    analysis_date = get_analysis_date(sgf_filename, game)
    analysis_filename = build_analysis_filename(analyses_directory, game, base_name, analysis_date)
    command, initial_player, positions = transform_sgf_to_command(game, convert=False)

    katago = get_katago()
    print('Sending game for analysis...')

    start = time.time()
    katago.write_message(command)
    analysis, total_visits = compose_analysis(katago, initial_player, positions, start, game)
    end = time.time()
    print(
        f'Game reviewed in {end - start:0.3f} seconds ({total_visits} total visits, '
        f'{total_visits / (end - start):0.3f} visits per second).'
    )

    save_analysis(analysis_filename, analysis)
    return analysis_filename


def load_sgf(sgf):
    print(f'Evaluating {sgf}...')
    with open(sgf, encoding='UTF8') as infile:
        contents = infile.read()
    main_variation = parse_sgf_contents(contents)
    print('Parsing SGF succeeded.')
    return main_variation


def get_analysis_date(sgf_filename, main_variation):
    setup_node = main_variation[0]
    if 'DT' in setup_node:
        # There are some SGFs - I'm looking at you, GoGoD - that do not store the DT field with the required format.
        # This is an attempt to convert non-standard representations to the correct format.
        source = setup_node['DT']
        parsed = dateparser.parse(source)
        if parsed:
            date = parsed.date().isoformat()
        else:
            print(f'The requested SGF has an invalid DT field.  Please fix it: {source}')
            sys.exit(2)
    else:
        date = get_file_creation_date_string(sgf_filename)
    return date


def get_file_creation_date_string(sgf):
    creation_date = os.path.getctime(sgf)
    local_time = time.localtime(creation_date)
    return time.strftime('%Y-%m-%d', local_time)


def build_analysis_filename(analyses_directory, game, base_name, analysis_date):
    root = game[0]
    black_name = root['PB']
    black_rank_value = '' if 'BR' not in root else root['BR']
    black_rank = re.sub(r'[-?]', '', black_rank_value)
    komi = 0 if 'KM' not in root else root['KM']
    handicap = '' if 'HA' not in root else root['HA']
    size = root['SZ'] if 'SZ' in root else 19
    white_name = root['PW']
    white_rank_value = '' if 'WR' not in root else root['WR']
    white_rank = re.sub(r'[-?]', '', white_rank_value)

    path = f'{analysis_date}__{size}x{size}-'
    if handicap:
        path += f'HA{handicap}-'
    path += f'{komi}-{white_name}-'
    if white_rank:
        path += f'{white_rank}-'
    path += f'vs-{black_name}'
    if black_rank:
        path += f'-{black_rank}'
    path += f'__{base_name}.csv'
    path = re.sub(r'\s+', '_', path)

    print('DEBUG: path is', path)

    return f'{analyses_directory}/{path}'


def compose_analysis(katago, first_player, move_count, start, game):
    # TODO: This logic needs to account for board transformations for properly handling the policy results.  Add this!
    second_player = 'W' if first_player == 'B' else 'B'
    analysis = [
        {
            'move': x + 1,
            'player': first_player if x % 2 == 0 else second_player,
            'before': 0.,
            'after': 0.,
            'delta': 0.,
            'mistake': 0
        }
        for x in range(move_count - 1)
    ]
    done = 0
    total_visits = 0
    line = None
    try:
        while done < move_count:
            result = katago.next_line()
            if not result:
                time.sleep(0.001)
                continue
            line_type, line = result
            if not (line_type == LineType.output and line and line.startswith('{')):
                time.sleep(0.001)
                continue

            output = json.loads(line.rstrip())

            turn = output['turnNumber']
            value = output['moveInfos'][0]['scoreLead']

            visits = sum(map(lambda node: node['visits'], output['moveInfos']))
            total_visits += visits
            if turn + 1 < move_count:
                current = analysis[turn]

                current['before'] = value

                move_entry = game[turn + 1]
                next_move = move_entry['B'] if 'B' in move_entry else move_entry['W']
                if not next_move:
                    next_move = 'pass'
                current['played'] = next_move

                policy = []
                i = 0
                for row in range(19, 0, -1):
                    for column in 'ABCDEFGHJKLMNOPQRST':
                        probability = output['policy'][i]
                        i += 1
                        if probability < 0:
                            continue
                        move_entry = f'{column}{row}'
                        policy.append([move_entry, probability])
                policy.append(['pass', output['policy'][i]])
                policy.sort(key=lambda x: x[1], reverse=True)
                move_entry = [x for x in enumerate(policy) if x[1][0] == next_move][0]

                best_move = output['moveInfos'][0]['move']
                best_move_entry = [x for x in enumerate(policy) if x[1][0] == best_move][0]

                best_policy = best_move_entry[1][1]
                favorite_policy = policy[0][1]
                played_policy = move_entry[1][1]

                current['policy'] = played_policy
                current['ranking'] = move_entry[0] + 1
                current['potential_moves'] = len(policy)
                current['favorite'] = policy[0][0]
                current['favorite_policy'] = favorite_policy
                current['favorite_played_delta'] = favorite_policy - played_policy
                current['best'] = best_move
                current['best_policy'] = best_policy
                current['best_ranking'] = best_move_entry[0] + 1
                current['favorite_best_delta'] = favorite_policy - best_policy
                print(current)
            if turn > 0:
                analysis[turn - 1]['after'] = -value
            done += 1

            elapsed = time.time() - start
            print(
                f'{done} moves analyzed.  Turn {turn} was searched for {visits} visits; '
                f'{elapsed:0.3f} seconds elapsed; {total_visits / elapsed:0.3f} VPS.'
            )
    except Exception as e:
        print(f'An exception occurred:\n  {e}\n  {line}')
        exit(3)

    print('All positions analyzed, compositing analysis...')

    # Developer's Note: (J. Craig, 2022-01-12)
    # Adding logic to track how each player's moves compared with the best move and policy favorite revealed that
    # KG's score estimation can be further off than I thought.  If the player plays the AI's best move, the move should
    # never be considered a mistake.  That position's score needs to be pushed to the previous move as the expected
    # result.
    for i in range(len(analysis) - 1, -1, -1):
        entry = analysis[i]
        if entry['played'] == entry['best']:
            entry['before'] = entry['after']
            entry['delta'] = 0
            entry['mistake'] = 0
            if i > 0:
                analysis[i - 1]['after'] = -entry['after']
        else:
            delta = entry['before'] - entry['after']
            entry['delta'] = delta
            if delta < 0.5:
                entry['mistake'] = 0
            else:
                entry['mistake'] = round(delta)

    print('Analysis complete.')

    return analysis, total_visits


def save_analysis(analysis_filename, analysis):
    print(f'Writing analysis to {analysis_filename}...')

    with open(analysis_filename, 'w', encoding='utf-8') as csvfile:
        csvfile.write(
            'Move,Player,Before,After,Delta,Mistake,Played,Played Policy,Played Ranking,Legal Moves,Favorite,Favorite '
            'Policy,Delta: Favorite to Played,Best,Best Policy,Best Ranking,Delta: Favorite to Best\n'
        )
        for entry in analysis:
            csvfile.write(
                ','.join(
                    [
                        str(entry['move']),
                        entry['player'],
                        str(entry['before']),
                        str(entry['after']),
                        str(entry['delta']),
                        str(entry['mistake']),
                        str(entry['played']),
                        str(entry['policy']),
                        str(entry['ranking']),
                        str(entry['potential_moves']),
                        str(entry['favorite']),
                        str(entry['favorite_policy']),
                        str(entry['favorite_played_delta']),
                        str(entry['best']),
                        str(entry['best_policy']),
                        str(entry['best_ranking']),
                        str(entry['favorite_best_delta'])
                    ]
                ) +
                '\n'
            )

    print('Analysis saved.')


def transform_to_performance_matrix(original_performances):
    return np.array([transform_performance(get_mistakes(x)) for x in original_performances])


def get_mistakes(performance):
    return performance[2]


def transform_performance(mistakes, include_length=True):
    elements, counts = np.unique(mistakes, return_counts=True)

    total_observations = 1
    mistake_values = 723  # 361 * 2 + 1; intentionally excessively large to capture every possible mistake magnitude
    observations = np.full(mistake_values, total_observations / float(mistake_values))

    for i, count in zip(elements, counts):
        observations[i] += count
        total_observations += count
    frequencies = observations / total_observations

    better_worse = np.zeros((mistake_values * 2,))
    for i, frequency in enumerate(frequencies):
        if i > 0:
            better_worse[i * 2] = frequencies[i - 1] + better_worse[(i - 1) * 2]
        if i < mistake_values:
            better_worse[i * 2 + 1] = 1. - better_worse[i * 2] - frequencies[i]

    if include_length:
        first = np.append([len(mistakes)], frequencies)
    else:
        first = frequencies
    return np.append(first, better_worse)


def scale(performance_matrix, parameters, include_length=True):
    def get_mean(index):
        return parameters['frequency_means'][index - 1] if include_length else parameters['frequency_means'][index]

    if not parameters:
        if include_length:
            parameters = {
                'length_mean': performance_matrix[:, 0].mean(),
                'length_std': performance_matrix[:, 0].std(),
                'frequency_means': performance_matrix[:, 1:].mean(axis=0),
                'frequency_std': np.max(performance_matrix[:, 1:].std(axis=0))
            }
        else:
            parameters = {
                'frequency_means': performance_matrix.mean(axis=0),
                'frequency_std': np.max(performance_matrix.std(axis=0))
            }

    scaled = np.copy(performance_matrix)
    if include_length:
        scaled[:, 0] = (performance_matrix[:, 0] - parameters['length_mean']) / parameters['length_std']

    iteration_start = 1 if include_length else 0
    for i in range(iteration_start, len(performance_matrix[0])):
        scaled[:, i] = (performance_matrix[:, i] - get_mean(i)) / parameters['frequency_std']

    return scaled


def summarize(analysis_filename):
    statistics = {
        key: {
            'moves': 0,
            'mistakes': 0,
            'p(mistake)': 0,
            'loss_total': 0,
            'loss_mean': 0.,
            'loss_std_dev': 0,
            'timeline': []
        }
        for key in ('B', 'W')
    }
    with open(analysis_filename, encoding='utf-8') as infile:
        reader = csv.reader(infile)
        for row in reader:
            if row[0] == 'Move':
                continue
            player = row[1]
            loss = int(row[5])
            stats = statistics[player]
            stats['moves'] += 1
            stats['timeline'].append(loss)
            if loss > 0:
                stats['mistakes'] += 1
    for key in ('B', 'W'):
        stats = statistics[key]
        mistakes = stats['mistakes']
        moves = stats['moves']
        timeline = stats['timeline']
        stats['p(mistake)'] = mistakes / moves
        stats['loss_total'] = np.sum(timeline)
        stats['loss_mean'] = np.mean(timeline)
        stats['loss_std_dev'] = np.std(timeline)
    return statistics


def print_neat_float(value):
    return f'{value:0.3f}'


if __name__ == '__main__':
    target = sys.argv[1]
    if os.path.isfile(target):
        run(target)
    else:
        print(f'ERROR! Received a path that does not exist: {target}')
