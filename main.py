# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.

import csv
import dateparser
import numpy as np
import os.path
import json
import sys
import time
import yaml

from glob import glob
from katago import KataGo, LineType
from load_statistics import load_performances
from parse import parse_sgf_contents, transform_sgf_to_command


def run(sgf_filename):
    configuration = load_configuration()
    parameters, transformation = load_parameters(configuration['transformation_parameters'])

    analysis_filename = get_or_create_analysis_file(sgf_filename, configuration['analyses_directory'], configuration['katago'])
    original_performances = load_performances(analysis_filename)
    performance_matrix = transform_to_performance_matrix(original_performances)
    scaled = scale(performance_matrix, parameters)
    transformed = scaled @ transformation
    summary = summarize(analysis_filename)

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


def get_or_create_analysis_file(sgf_filename, analyses_directory, katago_configuration):
    base_name = get_base_filename(sgf_filename)
    analysis_filename = find_existing_analysis(base_name, analyses_directory)
    if analysis_filename:
        print(f'Found {analysis_filename} .')
    else:
        analysis_filename = perform_analysis(sgf_filename, base_name, analyses_directory, katago_configuration)
    return analysis_filename


def get_base_filename(file):
    filename = os.path.basename(file)
    index = filename.rfind('.')
    if index != -1:
        filename = filename[:index]
    return filename


def find_existing_analysis(base_name, analyses_directory):
    if not analyses_directory.endswith('/'):
        analyses_directory += '/'
    needle = f'{analyses_directory}*_{base_name}.csv'
    haystack = [x for x in glob(needle)]
    return haystack[0] if haystack else None


def perform_analysis(sgf_filename, base_name, analyses_directory, katago_configuration):
    game = load_sgf(sgf_filename)
    analysis_date = get_analysis_date(sgf_filename, game)
    analysis_filename = build_analysis_filename(analyses_directory, base_name, analysis_date)
    command, initial_player, positions = transform_sgf_to_command(game, convert=False)

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
    print('KataGo started. Sending game for analysis...')

    start = time.time()
    katago.write_message(command)
    analysis, total_visits = compose_analysis(katago, initial_player, positions, start)
    end = time.time()
    print(
        f'Game reviewed in {end - start:0.3f} seconds ({total_visits} total visits, '
        f'{total_visits / (end - start):0.3f} visits per second).'
    )
    katago.kill()

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


def build_analysis_filename(analyses_directory, base_name, analysis_date):
    return f'{analyses_directory}/{analysis_date}_{base_name}.csv'


def compose_analysis(katago, first_player, move_count, start):
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
                analysis[turn]['before'] = value
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

    for entry in analysis:
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
        csvfile.write('Move,Player,Before,After,Delta,Mistake\n')
        for entry in analysis:
            csvfile.write(
                ','.join(
                    [
                        str(entry['move']),
                        entry['player'],
                        str(entry['before']),
                        str(entry['after']),
                        str(entry['delta']),
                        str(entry['mistake'])
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
