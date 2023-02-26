# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.
import csv
import json

import dateparser
import numpy as np
import os
import re
import sys
import time

import pandas as pd
import yaml

from glob import glob

from domain.color import Color
from domain.coordinate import Coordinate
from domain.game import Game
from domain.pass_enum import Pass
from domain.ruleset import Ruleset
from infographic import generate_infographic
from katago import KataGo, LineType
from kifu import print_kifu
from load_statistics import load_performances_new
from parse import parse_sgf_contents, transform_sgf_to_command
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from typing import Callable, Optional, List, Dict, Set

from plot import plot_distributions
from render import render_table

MAX_MISTAKE = 361. * 2.
MIDDLE = MAX_MISTAKE * 4.
BUCKETS = int(MAX_MISTAKE * 8 + 1)

katago: Optional[KataGo] = None
get_katago: Optional[Callable[[], KataGo]] = None


class ScoringProcedure:
    def __init__(self, hyperparameters_path):
        with open(hyperparameters_path, 'rb') as infile:
            configuration = np.load(infile, allow_pickle=True)
            self._lda: LinearDiscriminantAnalysis = configuration['lda'].item()
            self._magnitude: float = configuration['magnitude'].item()
            self._pca: PCA = configuration['pca'].item()
            self._reference: np.array = configuration['reference']
            self._start: np.array = configuration['start']
            self._worst: float = configuration['worst'].item()
            self._scale = configuration['best'] - self._worst

    def score(self, performance) -> float:
        features = ScoringProcedure._transform_to_features(performance)
        pca_space = self._pca.transform(features)
        lda_space = self._lda.transform(pca_space)
        proportion = (lda_space - self._start).dot(self._reference) / self._magnitude
        return 100. * (proportion - self._worst) / self._scale

    @staticmethod
    def _transform_to_features(performance) -> np.array:
        """The feature vector's composition:
            Number of moves / 200 (attempted normalization)
            p(Mistake)
            Distribution for deltas
            Cumulative proportion of moves better than the referred move score
            Cumulative proportion of moves worse than the referred move score"""
        moves = len(performance)
        total_observations = moves + 1

        observations = np.full(BUCKETS, 1. / BUCKETS)
        for move in performance:
            clamped = round(ScoringProcedure._clamp(move, -MAX_MISTAKE, MAX_MISTAKE) * 4)
            index = int(clamped + MIDDLE)
            observations[index] += 1
        distribution = observations / total_observations

        better = np.zeros(BUCKETS)
        worse = np.zeros(BUCKETS)
        for i, proportion in enumerate(distribution):
            if i > 0:
                better[i] = distribution[i - 1] + better[i - 1]
            if i < moves:
                worse[i] = 1. - better[i] - distribution[i]

        return np.append(
                [moves / 200., np.sum(performance >= 0.5) / moves],
                [distribution, better, worse]
            ).reshape(1, -1)

    @staticmethod
    def _clamp(value, minimum, maximum):
        if value < minimum:
            result = minimum
        elif value > maximum:
            result = maximum
        else:
            result = value
        return result


def run(sgf_filename):
    global katago

    configuration = load_configuration()
    prep_katago(configuration['katago'])
    procedure = ScoringProcedure(configuration['transformation_parameters'])
    game, black_name, white_name, winner = load_sgf(sgf_filename)
    analysis_filename = get_or_create_analysis_file(sgf_filename, configuration['analyses_directory'], game)
    original_performances = load_performances_new(analysis_filename)
    scored_performances = {k: procedure.score(v)[0] for k, v in original_performances.items()}
    summary = summarize(analysis_filename)

    print(f'\nOverall Quality: {scored_performances["Game"]:0.3f}')
    print(f'{black_name} (B)\'s Quality: {scored_performances["B"]:0.3f}')
    print(f'{white_name} (W)\'s Quality: {scored_performances["W"]:0.3f}\n')


    print('Rendering performance table...')
    performance_table = render_table(
        configuration['renders_directory'],
        analysis_filename,
        black_name,
        white_name,
        winner,
        scored_performances,
        summary['B'],
        summary['W']
    )

    print('Rendering kifu...')
    kifu = print_kifu(
        configuration['kifu_directory'],
        analysis_filename,
        game,
        performance_table.height
    )

    target_width = kifu.width + performance_table.width

    print('Rendering distribution plots...')
    expected_result, distribution = plot_distributions(
        configuration['plots_directory'],
        analysis_filename,
        black_name,
        white_name,
        target_width
    )

    print('Compiling final infographic...')
    infographic = generate_infographic(
        configuration,
        analysis_filename,
        game,
        kifu,
        performance_table,
        expected_result,
        distribution
    )

    print(f'\nYou can find your infographic at {infographic.filename} .')

    if katago:
        katago.kill()


def load_configuration():
    def is_ordinal(x):
        return type(x) == int and x > 0

    with open('configuration/application.yaml') as infile:
        configuration = yaml.safe_load(infile)

    test_configuration_value(configuration, 'analyses_directory', os.path.isdir)
    test_configuration_value(configuration, 'brand', os.path.isfile)
    test_configuration_value(configuration, 'infographics_directory', os.path.isdir)
    test_configuration_value(configuration, 'kifu_directory', os.path.isdir)
    test_configuration_value(configuration, 'plots_directory', os.path.isdir)
    test_configuration_value(configuration, 'renders_directory', os.path.isdir)
    test_configuration_value(configuration, 'transformation_parameters', os.path.isfile)
    test_configuration_value(configuration, 'buffer', is_ordinal)

    test_configuration_value(configuration, 'katago', lambda x: type(x) == dict)
    katago_entry = configuration['katago']
    test_configuration_value(katago_entry, 'executable', os.path.isfile)
    test_configuration_value(katago_entry, 'configuration', os.path.isfile)
    test_configuration_value(katago_entry, 'model', os.path.isfile)
    test_configuration_value(katago_entry, 'analysis_threads', is_ordinal)
    test_configuration_value(katago_entry, 'search_threads', is_ordinal)

    return configuration


def test_configuration_value(configuration, key, test):
    if not (key in configuration and test(configuration[key])):
        print(f'Check configuration/application.yaml\'s {key} value.')
        sys.exit(1)


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
                analysis_threads=katago_configuration['analysis_threads'],
                search_threads=katago_configuration['search_threads']
            )
            while not katago.ready:
                time.sleep(0.001)
            print('KataGo started.')

        return katago

    get_katago = created


def load_sgf(sgf):
    print(f'Evaluating {sgf}...')
    with open(sgf, encoding='UTF8') as infile:
        contents = infile.read()
    main_variation = parse_sgf_contents(contents)
    print('Parsing SGF succeeded.')

    root = main_variation[0]

    if not isinstance(root['PB'], str):
        root['PB'] = str(root['PB'])
    if not isinstance(root['PW'], str):
        root['PW'] = str(root['PW'])

    black_name = root['PB']
    white_name = root['PW']
    result = root['RE']
    if result.startswith('B+'):
        winner = 'B'
    elif result.startswith('W+'):
        winner = 'W'
    else:
        winner = None

    return main_variation, black_name, white_name, winner


def get_or_create_analysis_file(sgf_filename, analyses_directory, game):
    base_name = get_base_filename(sgf_filename)
    analysis_filename = find_existing_analysis(base_name, analyses_directory)
    if analysis_filename:
        print(f'Found {analysis_filename} .')
    else:
        analysis_filename = perform_analysis(sgf_filename, game, base_name, analyses_directory)
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


def perform_analysis(sgf_filename, game, base_name, analyses_directory):
    global katago

    analysis_date = get_analysis_date(sgf_filename, game)
    analysis_filename = build_analysis_filename(analyses_directory, game, base_name, analysis_date)
    command, initial_player, positions = transform_sgf_to_command(game, convert=False)

    katago = get_katago()
    print('Sending game for analysis...')

    start = time.time()
    katago.write_message(command)
    analysis = compose_analysis(initial_player, positions, start, game)
    elapsed = time.time() - start
    print(
        f'Game reviewed in {elapsed:0.3f} seconds ({elapsed / positions:0.3f} seconds per position).'
    )

    save_analysis(analysis_filename, analysis)
    return analysis_filename


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


def compose_analysis(first_player: str, move_count: int, start: float, sgf: List[Dict]) -> List[Dict]:
    # Prepare a state to update with analysis results.
    states = play_through_sgf(sgf)
    second_player = 'W' if first_player == 'B' else 'B'
    analysis = [
        {
            'move': i + 1,
            'player': first_player if i % 2 == 0 else second_player,
            'before': 0.,
            'after': 0.,
            'delta': 0.,
            'played': 'pass' if states[i + 1].previous_move == Pass.PASS else states[i + 1].previous_move.name,
            'best': None
        }
        for i in range(move_count - 1)
    ]
    done = 0
    line = None

    # Use each evaluation line KataGo generates to update the analysis state.
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

            if turn + 1 < move_count:
                current = analysis[turn]
                current['before'] = value
                current['best'] = output['moveInfos'][0]['move']
            if turn > 0:
                analysis[turn - 1]['after'] = -value
            done += 1

            elapsed = time.time() - start
            print(
                f'{done} positions analyzed.  Turn {turn} completed; {elapsed:0.3f} seconds elapsed; '
                f'{elapsed / done:0.3f} SPP.'
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
    # Developer's Note: (J. Craig, 2022-05-01)
    # I updated this logic to handle transformational equivalence.  If playing a move results in a move that results in
    # a transformation of the board of KG's favorite move, the player is considered to have played the best move.
    for i in range(len(analysis) - 1, -1, -1):
        entry = analysis[i]
        actual_state = states[i + 1]
        previous_state = actual_state.previous_state
        best_move = Pass.PASS if entry['best'] == 'pass' else Coordinate[entry['best']]
        if (
            entry['played'] == entry['best'] or
            actual_state.board.canonical_code == previous_state.play(best_move).canonical_code
        ):
            entry['before'] = entry['after']
            entry['delta'] = 0
            if i > 0:
                analysis[i - 1]['after'] = -entry['after']
        else:
            delta = entry['before'] - entry['after']
            entry['delta'] = delta

    print('Analysis complete.')

    return analysis


def play_through_sgf(sgf: List[Dict]) -> List[Game]:
    root = sgf[0]
    ruleset = get_ruleset(root)
    komi = get_komi(root, ruleset)
    handicap_stones = get_handicap_stones(root)

    game = Game(ruleset=ruleset, komi=komi, handicap_stones=handicap_stones)
    states = [game]
    for node in sgf:
        black_played = 'B' in node
        white_played = 'W' in node
        if not (black_played or white_played):
            continue

        move_representation = node['B'] if black_played else node['W']
        if not move_representation:
            move = Pass.PASS
        else:
            move = Coordinate[move_representation]

        if black_played:
            if game.current_player != Color.BLACK:
                game = game.play(Pass.PASS)
        else:
            if game.current_player != Color.WHITE:
                game = game.play(Pass.PASS)

        try:
            game = game.play(move)
            states.append(game)
        except Exception:
            print(f'Move {move} was found to be illegal in this state!')
            print(game)

    return states


def get_ruleset(root: dict) -> Ruleset:
    ruleset = None
    if 'RU' in root:
        needle = simplify(root['RU'])
        for candidate in Ruleset:
            name = simplify(candidate.name)
            if needle == name:
                ruleset = candidate
                break
        if not ruleset:
            first = needle[0]
            for candidate in Ruleset:
                if first[0] == candidate[0]:
                    ruleset = candidate
                    break
        if not ruleset:
            print(f'WARNING: Could not interpret RU property as a ruleset KataGo knows.  Using JAPANESE: {root["RU"]}')
            ruleset = Ruleset.JAPANESE
    else:
        ruleset = Ruleset.JAPANESE
    return ruleset


def simplify(text: str) -> str:
    lowercase = text.upper()
    return re.sub(r'[^A-Z]+', '', lowercase)


def get_komi(root: dict, ruleset: Ruleset) -> float:
    if 'KM' in root:
        komi = root['KM']
    elif ruleset in (Ruleset.JAPANESE, Ruleset.KOREAN):
        komi = 6.5
    elif ruleset in (Ruleset.NEW_ZEALAND, Ruleset.TROMP_TAYLOR):
        komi = 7
    elif ruleset in (
        Ruleset.AGA,
        Ruleset.AGA_BUTTON,
        Ruleset.BGA,
        Ruleset.CHINESE,
        Ruleset.CHINESE_KGS,
        Ruleset.CHINESE_OGS
    ):
        komi = 7.5
    else:
        print(f'Could not figure out what komi to use from the SGF and {ruleset} Ruleset; using 6.5.')
        komi = 6.5
    return komi


def get_handicap_stones(root: dict) -> Set[Coordinate]:
    if 'AB' in root:
        found = root['AB']
        if isinstance(found, str):
            found = [found]
        handicap_stones = {Coordinate[c] for c in found}
    else:
        handicap_stones = set()
    return handicap_stones


def save_analysis(analysis_filename: str, analysis: List[Dict]):
    print(f'Writing analysis to {analysis_filename}...')

    with open(analysis_filename, 'w', encoding='utf-8') as csvfile:
        csvfile.write('Move,Player,Before,After,Delta,Played,Best\n')
        for entry in analysis:
            csvfile.write(
                ','.join(
                    [
                        str(entry['move']),
                        entry['player'],
                        str(entry['before']),
                        str(entry['after']),
                        str(entry['delta']),
                        str(entry['played']),
                        str(entry['best'])
                    ]
                ) +
                '\n'
            )

    print('Analysis saved.')


def summarize(analysis_filename: str) -> dict:
    dataframe = pd.read_csv(analysis_filename)

    statistics = dict()
    for key in ('B', 'W'):
        indices = dataframe['Player'] == key
        player_rows = dataframe[indices]
        deltas = player_rows['Delta'].to_numpy()
        mistakes = np.array([int(round(d)) for d in deltas])

        moves = len(mistakes)
        mistake_count = np.sum(mistakes >= 1)
        p_mistake = float(mistake_count) / moves
        loss_total = np.sum(mistakes)
        loss_mean = loss_total / moves
        loss_std_dev = np.std(deltas)

        statistics[key] = {
            'moves': moves,
            'mistakes': mistake_count,
            'p(mistake)': p_mistake,
            'loss_total': int(loss_total),
            'loss_mean': loss_mean,
            'loss_std_dev': loss_std_dev,
            'timeline': mistakes
        }

    return statistics


if __name__ == '__main__':
    target = sys.argv[1]
    if os.path.isfile(target):
        run(target)
    else:
        print(f'ERROR! Received a path that does not exist: {target}')
    pass
