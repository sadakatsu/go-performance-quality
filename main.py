# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.
import json

import dateparser
import jsons
import numpy as np
import os
import re
import sys
import time

import katago as kg
import pandas as pd
import yaml

from glob import glob

from composeanalysis.compose_analysis import compose_analysis
from domain.color import Color
from domain.coordinate import Coordinate
from domain.game import Game
from domain.pass_enum import Pass
from domain.ruleset import Ruleset
from infographic import generate_infographic
from katago import Engine, LaunchConfiguration, HumanProfile
from katago.response import SuccessResponse, MoveInfo
from kifu import print_kifu
from load_statistics import load_performances_new
from parse import parse_sgf_contents, transform_sgf_to_query
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from typing import Callable, Optional, List, Dict, Set, Union, Any

from plot import plot_distributions
from render import render_table

EPSILON = np.finfo(float).eps
MAX_MISTAKE = 361. * 2.
MIDDLE = MAX_MISTAKE * 4.
BUCKETS = int(MAX_MISTAKE * 8 + 1)

katago: Optional[Engine] = None
get_katago: Optional[Callable[[], Engine]] = None


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

    def score(self, performance) -> Union[float, np.array]:
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
    game, black_name, white_name, size, winner = load_sgf(sgf_filename)
    analysis_filename = get_or_create_analysis_file(sgf_filename, configuration, game)
    original_performances = load_performances_new(analysis_filename)

    scored_performances = {
        k1: {k2: procedure.score(v2)[0] for k2, v2 in v1.items()} for k1, v1 in original_performances.items()
    }

    summary = summarize(analysis_filename)

    print(f'\nOverall Quality: {scored_performances["Game"]["actual"]:0.3f}')
    print(f'{black_name} (B)\'s Quality: {scored_performances["B"]["actual"]:0.3f}')
    print(f'{white_name} (W)\'s Quality: {scored_performances["W"]["actual"]:0.3f}\n')


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
        size,
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
    def is_bool(x):
        return x and str(x).lower() in ('true', 'false')

    def is_dict(x):
        return type(x) == dict

    def is_float(x):
        return type(x) == float

    def is_ordinal(x):
        return type(x) == int and x > 0

    def is_str(x):
        return x and len(str(x).strip()) > 0

    with open('configuration/application.yaml') as infile:
        configuration = yaml.safe_load(infile)

    test_configuration_value(configuration, 'analyses_directory', os.path.isdir)
    test_configuration_value(configuration, 'brand', os.path.isfile)
    test_configuration_value(configuration, 'buffer', is_ordinal)
    test_configuration_value(configuration, 'infographics_directory', os.path.isdir)
    test_configuration_value(configuration, 'kifu_directory', os.path.isdir)
    test_configuration_value(configuration, 'plots_directory', os.path.isdir)
    test_configuration_value(configuration, 'renders_directory', os.path.isdir)
    test_configuration_value(configuration, 'threads', is_ordinal)
    test_configuration_value(configuration, 'transformation_parameters', os.path.isfile)

    test_configuration_value(configuration, 'katago', is_dict)
    katago_entry = configuration['katago']
    test_configuration_value(katago_entry, 'analysisThreads', is_ordinal)
    test_configuration_value(katago_entry, 'config', os.path.isfile)
    test_configuration_value(katago_entry, 'executable', os.path.isfile)
    test_configuration_value(katago_entry, 'fastQuit', is_bool)
    test_configuration_value(katago_entry, 'humanModel', os.path.isfile)
    test_configuration_value(katago_entry, 'playouts', is_ordinal)
    test_configuration_value(katago_entry, 'profile', is_str)
    test_configuration_value(katago_entry, 'searchModel', os.path.isfile)
    test_configuration_value(katago_entry, 'searchThreads', is_ordinal)
    test_configuration_value(katago_entry, 'visits', is_ordinal)

    test_configuration_value(configuration, 'accuracy', is_dict)
    accuracy_entry = configuration['accuracy']
    test_configuration_value(accuracy_entry, 'lead_drop', is_float)
    test_configuration_value(accuracy_entry, 'max_visit_ratio', is_float)
    test_configuration_value(accuracy_entry, 'top_moves', is_ordinal)
    test_configuration_value(accuracy_entry, 'winrate_drop', is_float)

    configuration['katago'] = LaunchConfiguration.from_dict(katago_entry)

    return configuration


def test_configuration_value(configuration, key, test):
    if not (key in configuration and test(configuration[key])):
        print(f'Check configuration/application.yaml\'s {key} value.')
        sys.exit(1)


def prep_katago(launch_config: LaunchConfiguration):
    global get_katago, katago

    def created():
        global katago

        if not katago:
            print('Starting KataGo...')
            # katago = KataGo(
            #     katago_configuration['executable'],
            #     katago_configuration['configuration'],
            #     katago_configuration['model'],
            #     analysis_threads=katago_configuration['analysis_threads'],
            #     search_threads=katago_configuration['search_threads'],
            #     max_playouts=katago_configuration['max_playouts'],
            #     max_visits=katago_configuration['max_visits'],
            # )
            katago = Engine(launch_config)
            while not katago.ready:
                time.sleep(1)
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
    result = '?' if 'RE' not in root else root['RE']

    # We now require a SZ attribute.
    if 'SZ' not in root:
        root['SZ'] = 19
    size = root['SZ']

    if result.startswith('B+'):
        winner = 'B'
    elif result.startswith('W+'):
        winner = 'W'
    else:
        winner = None

    return main_variation, black_name, white_name, size, winner


required_headers = {
    'Move',
    'Player',
    'Prior Lead',
    'Posterior Lead',
    'Loss',
    'Prior Win Rate',
    'Posterior Win Rate',
    'Drop',
    'Played',
    'Played Search',
    'Best',
    'Best Search',
    'Counts as Best',
    'Counts as Match',
    'Expected Loss',
    'Random',
    '20k',
    '19k',
    '18k',
    '17k',
    '16k',
    '15k',
    '14k',
    '13k',
    '12k',
    '11k',
    '10k',
    '9k',
    '8k',
    '7k',
    '6k',
    '5k',
    '4k',
    '3k',
    '2k',
    '1k',
    '1d',
    '2d',
    '3d',
    '4d',
    '5d',
    '6d',
    '7d',
    '8d',
    '9d',
    'Pro',
    'AI',
    '20k Policy',
    '19k Policy',
    '18k Policy',
    '17k Policy',
    '16k Policy',
    '15k Policy',
    '14k Policy',
    '13k Policy',
    '12k Policy',
    '11k Policy',
    '10k Policy',
    '9k Policy',
    '8k Policy',
    '7k Policy',
    '6k Policy',
    '5k Policy',
    '4k Policy',
    '3k Policy',
    '2k Policy',
    '1k Policy',
    '1d Policy',
    '2d Policy',
    '3d Policy',
    '4d Policy',
    '5d Policy',
    '6d Policy',
    '7d Policy',
    '8d Policy',
    '9d Policy',
    'Pro Policy',
    'AI Policy',
    'Search',
}


def get_or_create_analysis_file(sgf_filename, configuration, game):
    base_name = get_base_filename(sgf_filename)

    # We can reuse a previously generated analysis if the CSV file exists and it captures the data necessary for this
    # GPQ version.
    needs_analysis = True
    analyses_directory = configuration['analyses_directory']
    analysis_filename = find_existing_analysis(base_name, analyses_directory)
    if analysis_filename:
        print(f'Found {analysis_filename} .')
        headers = set(pd.read_csv(analysis_filename, index_col=False, nrows=0).columns.to_list())

        needs_analysis = False
        for required_header in required_headers:
            if required_header not in headers:
                print(f'Missing required header "{required_header}".  Rerunning analysis to generate up-to-date file.')
                needs_analysis = True
                break

    # Run the analysis only if it is needed.
    if needs_analysis:
        analysis_filename = perform_analysis(
            sgf_filename,
            game,
            base_name,
            analyses_directory,
            configuration
        )

    # Return the analysis filename.
    return analysis_filename


def get_base_filename(file):
    filename = os.path.basename(file)
    index = filename.rfind('.')
    if index != -1:
        filename = filename[:index]
    return re.sub(r'[^\w.-]+', '_', filename)


def find_existing_analysis(base_name, analyses_directory):
    if not analyses_directory.endswith('/'):
        analyses_directory += '/'
    needle = f'{analyses_directory}*_{base_name}.csv'
    haystack = [x for x in glob(needle)]
    return haystack[0] if haystack else None


def perform_analysis(
    sgf_filename,
    game,
    base_name,
    analyses_directory,
    configuration: Dict
):
    global katago

    analysis_date = get_analysis_date(sgf_filename, game)
    analysis_filename = build_analysis_filename(analyses_directory, game, base_name, analysis_date)
    query, initial_player, positions = transform_sgf_to_query(game)
    query.include_ownership = True

    katago = get_katago()
    print('Sending game for analysis...')

    # We need to publish a deep query for the analysis and incredibly shallow queries to get the human policy values.
    # We need to track each of these
    start = time.time()
    query_ids: Dict[Optional[HumanProfile], str] = {}
    query_ids[None] = katago.write_query(query)

    query.include_ownership = False
    query.max_visits = 1
    query.analyze_turns.pop()  # we don't need the last turn analyzed because there is no following turn to score
    for human_profile in HumanProfile:
        # TODO: Do I want to add this to the configuration file in the future?
        name = human_profile.value
        if name.startswith('preaz') or name.startswith('pro') and not name.endswith('2023'):
            continue
        query.set_human_profile(human_profile)
        query_ids[human_profile] = katago.write_query(query)

    analysis = compose_analysis(katago, positions, start, game, configuration, query_ids)
    elapsed = time.time() - start
    print(
        f'Game reviewed in {elapsed:0.3f} seconds.'
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
            # TEMPORARY HACK because of GoGoD
            match = re.search(r'^(\d{4}-\d{1,2}-\d{1,2})', source)
            if match:
                parsed = dateparser.parse(match.group(0))
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
    path = re.sub(r'[^\w.\- ]+', '_', path)

    print('DEBUG: path is', path)

    return f'{analyses_directory}/{path}'


def map_move_to_identicals(current_state: Game) -> Dict[Union[Coordinate, Pass], Set[Union[Coordinate, Pass]]]:
    move_to_code: Dict[Union[Coordinate, Pass], str] = {}
    code_to_moves: Dict[str, Set[Union[Coordinate, Pass]]] = {}
    for move in current_state.legal_moves:
        code: str = current_state.play(move).canonical_code
        move_to_code[move] = code
        if code in code_to_moves:
            code_to_moves[code].add(move)
        else:
            code_to_moves[code] = {move}
    print('.', end='')
    sys.stdout.flush()
    return {move: code_to_moves[code] for move, code in move_to_code.items()}


# def compose_analysis(
#     first_player: str,
#     move_count: int,
#     start: float,
#     sgf: List[Dict],
#     configuration: Dict,
#     query_ids: Dict[Optional[HumanProfile], str],
# ) -> List[Dict]:
#     # Prepare a state to update with analysis results.
#     states = play_through_sgf(sgf)
#     second_player = 'W' if first_player == 'B' else 'B'
#     analysis = [
#         {
#             'move': i + 1,
#             'player': first_player if i % 2 == 0 else second_player,
#             'prior lead': 0.,
#             'posterior lead': 0.,
#             'loss': 0.,
#             'prior win rate': 0.,
#             'posterior win rate': 0.,
#             'drop': 0.,
#             'played': 'pass' if states[i + 1].previous_move == Pass.PASS else states[i + 1].previous_move.name,
#             'best': None,
#             'played search': 0,
#             'best search': 0,
#             'counts as best': 0,
#             'counts as match': 0,
#             'expected loss': 0.,
#             'priors': {},
#             'policies': {},
#         }
#         for i in range(move_count - 1)
#     ]
#     done = 0
#     line = None
#
#     size: int = int(sgf[0]['SZ'])
#     last_index: int = size * size
#
#     lead_drop = configuration['accuracy']['lead_drop']
#     max_visit_ratio = configuration['accuracy']['max_visit_ratio']
#     top_moves = configuration['accuracy']['top_moves'] - 1  # order starts at zero
#     winrate_drop = configuration['accuracy']['winrate_drop']
#
#     # First, generate all the transformational invariance information for each game state.  My Go domain library is very
#     # slow in Python.  Having all this information preprocessed using multithreading should rapidly accelerate the
#     # analysis, especially on moderately powerful CPUs.
#     print('Processing transformationally identical moves across whole game history...')
#     pool = Pool(min(configuration['threads'], len(states)))
#     history_move_to_identicals: List[Dict[Union[Coordinate, Pass], Set[Union[Coordinate, Pass]]]] = (
#         pool.map(map_move_to_identicals, states)
#     )
#     print()
#     elapsed = time.time() - start
#     print(f'Processed in {elapsed:0.3f} s.')
#
#     # Use each evaluation line KataGo generates to update the analysis state.
#     search_id = query_ids[None]
#     try:
#         while done < move_count:
#             # Get the next response.
#             result: SuccessResponse = katago.next_response(search_id)
#             if not result:
#                 time.sleep(1)
#                 continue
#
#             # If this is any position but the last, compile the simplified raw representation for the CSV file and grab
#             # the expected loss for the Simplicity metric.
#             turn = result.turn_number
#             if turn + 1 < move_count:
#                 # policy: Dict[str, float] = {}
#                 # for i, value in enumerate(result.human_policy):
#                 #     if value < -0.5:
#                 #         continue
#                 #     label = index_to_coordinate_label(i, size)
#                 #     policy[label] = value
#
#                 ownership: Dict[str, float] = {}
#                 for i, value in enumerate(result.ownership):
#                     label = index_to_coordinate_label(i, size)
#                     ownership[label] = value
#
#                 analysis[turn]['search'] = {
#                     'turnNumber': turn,
#                     'rootInfo': {
#                         'currentPlayer': result.root_info.current_player.name,
#                         'visits': result.root_info.visits,
#                     },
#                     'policy': result.policy,
#                     'ownership': ownership,
#                     'moveInfos': [
#                         {
#                             'isSymmetryOf': x.is_symmetry_of,
#                             'move': x.move.name,
#                             'order': x.order,
#                             'prior': x.prior,
#                             'scoreLead': x.score_lead,
#                             'visits': x.visits,
#                             'winrate': x.winrate,
#                         } for x in result.move_infos
#                     ]
#                 }
#
#                 # TODO: This algorithm is not quite correct.  Correct to account for probability of moves not checked.
#                 best_score = result.move_infos[0].score_lead
#                 expected_loss = 0.
#                 for m in result.move_infos:
#                     prior = m.prior
#                     loss = best_score - m.score_lead
#                     expected_loss += prior * loss
#                 analysis[turn]['expected loss'] = expected_loss
#
#             move_to_identicals: Dict[Union[Coordinate, Pass], Set[Union[Coordinate, Pass]]] = (
#                 history_move_to_identicals[turn]
#             )
#
#             # Treat transformationally identical moves as being the same by keeping only the most searched branch
#             # for each set.
#             kept: Dict[Union[Coordinate, Pass], MoveInfo] = {}
#             for move_info in result.move_infos:
#                 # This is necessary because we have two different Coordinate/Pass class pairs.  The MoveInfo one comes
#                 # from the katago module.  The one we are using here comes from the domain package.  We need to map
#                 # them.
#                 move_label = move_info.move.name
#                 move = Coordinate[move_label] if move_label.lower() != 'pass' else Pass.PASS
#                 visits = move_info.visits
#                 if move not in kept or kept[move].visits < visits:
#                     for m in move_to_identicals[move]:
#                         kept[m] = move_info
#
#             # Build the simplified list of moves using this mapping.
#             # TODO: This code looks like it builds the same list as before.
#             seen: Set[Union[kg.Coordinate, kg.Pass]] = set()
#             kept_list: List[MoveInfo] = []
#             for move, move_info in kept.items():
#                 if move not in seen:
#                     seen.add(move)
#                     kept_list.append(move_info)
#             kept_list = sorted(kept_list, key=lambda m: m.order)
#
#             # Relabel all the order values in the move infos.  This gives us control over whether to consider moves
#             # as equivalent.
#             order = -1
#             previous: Optional[MoveInfo] = None
#             threshold = np.floor(kept_list[0].visits * max_visit_ratio)
#             for index, move_info in enumerate(kept_list):
#                 if (
#                     previous is None or
#                     move_info.visits < threshold or
#                     move_info.winrate + winrate_drop - EPSILON < previous.winrate or
#                     move_info.score_lead + lead_drop - EPSILON < previous.score_lead
#                 ):
#                     order = index
#                     previous = move_info
#                 move_info.order = order
#
#             # Capture the data needed for tracking Accuracy, Match %, Best Move %, and for determining whether the
#             # player is playing like a bot or beginner.
#             if turn + 1 < move_count:
#                 current = analysis[turn]
#                 current['best search'] = kept_list[0].visits
#
#                 played_move = states[turn + 1].previous_move
#                 if played_move in kept:
#                     played_move_info = kept[played_move]
#                     current['played search'] = played_move_info.visits
#
#                     identical_to_played = move_to_identicals[played_move]
#                     counts_as_best = 0
#                     counts_as_match = 0
#                     for move_info in kept_list:
#                         order = move_info.order
#                         if order > top_moves:
#                             break
#
#                         visits = move_info.visits
#                         if visits < threshold:
#                             continue
#
#                         move = Pass.PASS if move_info.move == kg.Pass.PASS else Coordinate[move_info.move.name]
#                         if move in identical_to_played:
#                             counts_as_match = 1
#                             if order == 0:
#                                 counts_as_best = 1
#                             break
#                     current['counts as best'] = counts_as_best
#                     current['counts as match'] = counts_as_match
#                 else:
#                     current['played search'] = 0
#                     current['counts as best'] = 0
#                     current['counts as match'] = 0
#
#                 index = coordinate_label_to_index(played_move.name, size)
#                 current['priors']['AI'] = result.policy[index]
#
#                 # Count the number of legal moves to estimate the beginner's prior for the move.
#                 legal_move_count: int = sum(1 for x in result.policy if x > -0.5)
#                 current['priors']['random'] = 1. / legal_move_count
#
#                 # NEW ADDITION: Construct the policy information for this turn.  We will need things like the max
#                 # likelihood and possibly more to determine the move rating stats.
#                 policy: Dict[str, float] = {}
#                 for i, value in enumerate(result.policy):
#                     if value < -0.5:
#                         continue
#                     label = index_to_coordinate_label(i, size)
#                     policy[label] = value
#
#                 current['policies']['AI'] = policy
#
#             # Perform the rest of the GPQ logic (most of which was written before I bothered to comment anything).
#             lead = kept_list[0].score_lead
#             winrate = kept_list[0].winrate
#
#             if turn + 1 < move_count:
#                 current['prior lead'] = lead
#                 current['prior win rate'] = winrate
#                 current['best'] = kept_list[0].move.name
#             if turn > 0:
#                 analysis[turn - 1]['posterior lead'] = -lead
#                 analysis[turn - 1]['posterior win rate'] = 1. - winrate
#
#             # Track the progress.
#             done += 1
#
#             elapsed = time.time() - start
#             print(
#                 f'{done} positions analyzed.  Turn {turn} completed; {elapsed:0.3f} seconds elapsed; '
#                 f'{elapsed / done:0.3f} SPP.'
#             )
#
#     except Exception as e:
#         print(f'An exception occurred:\n  {e}\n  {line}')
#         traceback.print_exc(file=sys.stdout)
#         exit(3)
#
#     print('All positions analyzed.  Retrieving human profile priors...')
#     profiles_complete: int = 0
#     total_profiles: int = (len(query_ids) - 1) * (move_count - 1)
#     while profiles_complete < total_profiles:
#         found = False
#         for human_profile, query_id in query_ids.items():
#             result = katago.next_response(query_id)
#             if result is None:
#                 continue
#
#             profiles_complete += 1
#             found = True
#
#             if profiles_complete == total_profiles // 100:
#                 print('.', end='')
#                 sys.stdout.flush()
#
#             previous = analysis[result.turn_number]
#
#             index: int
#             played_label: str = previous['played']
#             if played_label == 'pass':
#                 index = last_index
#             else:
#                 index = coordinate_label_to_index(played_label, size)
#             prior: float = result.human_policy[index]
#
#             profile_label: str = 'pro' if human_profile.value.startswith('pro') else human_profile.value.split('_')[1]
#
#             previous['priors'][profile_label] = prior
#
#             # NEW ADDITION: Construct the policy information for this turn.  We will need things like the max likelihood
#             # and possibly more to determine the move rating stats.
#             policy: Dict[str, float] = {}
#             for i, value in enumerate(result.human_policy):
#                 if value < -0.5:
#                     continue
#                 label = index_to_coordinate_label(i, size)
#                 policy[label] = value
#
#             previous['policies'][profile_label] = policy
#
#         if profiles_complete < total_profiles and not found:
#             time.sleep(1)
#     elapsed = time.time() - start
#     print()
#     print(f'Finished all evaluation consumption in {elapsed:0.3f} s.  Processing...')
#
#     # Developer's Note: (J. Craig, 2022-01-12)
#     # Adding logic to track how each player's moves compared with the best move and policy favorite revealed that
#     # KG's score estimation can be further off than I thought.  If the player plays the AI's best move, the move should
#     # never be considered a mistake.  That position's score needs to be pushed to the previous move as the expected
#     # result.
#     # Developer's Note: (J. Craig, 2022-05-01)
#     # I updated this logic to handle transformational equivalence.  If playing a move results in a move that results in
#     # a transformation of the board of KG's favorite move, the player is considered to have played the best move.
#     for i in range(len(analysis) - 1, -1, -1):
#         entry = analysis[i]
#         actual_state = states[i + 1]
#         previous_state = actual_state.previous_state
#         best_move = Pass.PASS if entry['best'].lower() == 'pass' else Coordinate[entry['best']]
#         if (
#             entry['played'] == entry['best'] or
#             actual_state.board.canonical_code == previous_state.play(best_move).canonical_code
#         ):
#             entry['prior lead'] = entry['posterior lead']
#             entry['loss'] = 0
#             entry['prior win rate'] = entry['posterior win rate']
#             entry['drop'] = 0
#             if i > 0:
#                 analysis[i - 1]['posterior lead'] = -entry['posterior lead']
#                 analysis[i - 1]['posterior win rate'] = 1. - entry['posterior win rate']
#         else:
#             loss = entry['prior lead'] - entry['posterior lead']
#             entry['loss'] = loss
#             drop = entry['prior win rate'] - entry['posterior win rate']
#             entry['drop'] = drop
#
#     print('Analysis complete.')
#
#     return analysis


def coordinate_label_to_index(played_label, size):
    if not played_label or played_label.lower() == 'pass':
        result = size * size
    else:
        row: int = size - int(played_label[1:])
        column: int = 'ABCDEFGHJKLMNOPQRST'.index(played_label[0])
        result = row * size + column
    return result


def index_to_coordinate_label(index: int, size: int) -> str:
    if index == size * size:
        result = 'pass'
    else:
        # THESE LINES ARE COMMENTED OUT TO REMIND ME TO CHECK MY MATH BEFORE GETTING SO MUCH FARTHER IN THE PROJECT  }:|
        # column_index = index // size
        column_index = index % size
        column = 'ABCDEFGHJKLMNOPQRST'[column_index]

        # row_index = index % size
        row_index = index // size
        row = size - row_index

        result = f'{column}{row}'

    return result


def play_through_sgf(sgf: List[Dict]) -> List[Game]:
    root = sgf[0]
    ruleset = get_ruleset(root)
    komi = get_komi(root, ruleset)
    handicap_stones = get_handicap_stones(root)

    # TODO: Revise this code to support initial positions other than just handicap stones.  Fox "tests" new accounts by
    #  throwing them into a populated board at the start of the middle game.
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
                if first == candidate.name[0]:
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
        if int(komi) == komi and komi > 99:
            if komi % 100 == 50:
                komi /= 100.  # Tygem
            else:
                komi /= 50.  # Fox
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
        csvfile.write(
            'Move,Player,Prior Lead,Posterior Lead,Loss,Prior Win Rate,Posterior Win Rate,Drop,Played,Played Search,'
            'Best,Best Search,Counts as Best,Counts as Match,Expected Loss,Random,20k,19k,18k,17k,16k,15k,14k,13k,'
            '12k,11k,10k,9k,8k,7k,6k,5k,4k,3k,2k,1k,1d,2d,3d,4d,5d,6d,7d,8d,9d,Pro,AI,20k Policy,19k Policy,18k Policy,'
            '17k Policy,16k Policy,15k Policy,14k Policy,13k Policy,12k Policy,11k Policy,10k Policy,9k Policy,'
            '8k Policy,7k Policy,6k Policy,5k Policy,4k Policy,3k Policy,2k Policy,1k Policy,1d Policy,2d Policy,'
            '3d Policy,4d Policy,5d Policy,6d Policy,7d Policy,8d Policy,9d Policy,Pro Policy,AI Policy,Search\n'
        )

        for entry in analysis:
            columns = [
                str(entry['move']),
                entry['player'],
                str(entry['prior lead']),
                str(entry['posterior lead']),
                str(entry['loss']),
                str(entry['prior win rate']),
                str(entry['posterior win rate']),
                str(entry['drop']),
                str(entry['played']),
                str(entry['played search']),
                str(entry['best']),
                str(entry['best search']),
                str(entry['counts as best']),
                str(entry['counts as match']),
                str(entry['expected loss']),
                str(entry['priors']['random']),
                str(entry['priors']['20k']),
                str(entry['priors']['19k']),
                str(entry['priors']['18k']),
                str(entry['priors']['17k']),
                str(entry['priors']['16k']),
                str(entry['priors']['15k']),
                str(entry['priors']['14k']),
                str(entry['priors']['13k']),
                str(entry['priors']['12k']),
                str(entry['priors']['11k']),
                str(entry['priors']['10k']),
                str(entry['priors']['9k']),
                str(entry['priors']['8k']),
                str(entry['priors']['7k']),
                str(entry['priors']['6k']),
                str(entry['priors']['5k']),
                str(entry['priors']['4k']),
                str(entry['priors']['3k']),
                str(entry['priors']['2k']),
                str(entry['priors']['1k']),
                str(entry['priors']['1d']),
                str(entry['priors']['2d']),
                str(entry['priors']['3d']),
                str(entry['priors']['4d']),
                str(entry['priors']['5d']),
                str(entry['priors']['6d']),
                str(entry['priors']['7d']),
                str(entry['priors']['8d']),
                str(entry['priors']['9d']),
                str(entry['priors']['pro']),
                str(entry['priors']['AI']),
                csv_escape_json(entry['policies']['20k']),
                csv_escape_json(entry['policies']['19k']),
                csv_escape_json(entry['policies']['18k']),
                csv_escape_json(entry['policies']['17k']),
                csv_escape_json(entry['policies']['16k']),
                csv_escape_json(entry['policies']['15k']),
                csv_escape_json(entry['policies']['14k']),
                csv_escape_json(entry['policies']['13k']),
                csv_escape_json(entry['policies']['12k']),
                csv_escape_json(entry['policies']['11k']),
                csv_escape_json(entry['policies']['10k']),
                csv_escape_json(entry['policies']['9k']),
                csv_escape_json(entry['policies']['8k']),
                csv_escape_json(entry['policies']['7k']),
                csv_escape_json(entry['policies']['6k']),
                csv_escape_json(entry['policies']['5k']),
                csv_escape_json(entry['policies']['4k']),
                csv_escape_json(entry['policies']['3k']),
                csv_escape_json(entry['policies']['2k']),
                csv_escape_json(entry['policies']['1k']),
                csv_escape_json(entry['policies']['1d']),
                csv_escape_json(entry['policies']['2d']),
                csv_escape_json(entry['policies']['3d']),
                csv_escape_json(entry['policies']['4d']),
                csv_escape_json(entry['policies']['5d']),
                csv_escape_json(entry['policies']['6d']),
                csv_escape_json(entry['policies']['7d']),
                csv_escape_json(entry['policies']['8d']),
                csv_escape_json(entry['policies']['9d']),
                csv_escape_json(entry['policies']['pro']),
                csv_escape_json(entry['policies']['AI']),
                csv_escape_json(entry['search']),
            ]

            csvfile.write(','.join(columns) + '\n')

    print('Analysis saved.')


def csv_escape_json(raw: Any) -> str:
    return f'''"{json.dumps(raw).replace('"', '""')}"'''


def summarize(analysis_filename: str) -> dict:
    dataframe = pd.read_csv(analysis_filename)
    dataframe['Search'] = dataframe[['Played Search', 'Best Search']].min(axis=1)

    statistics = dict()
    for key in ('B', 'W'):
        indices = dataframe['Player'] == key
        player_rows = dataframe[indices]
        losses = player_rows['Loss'].to_numpy()
        mistakes = np.array([int(round(d)) for d in losses])

        moves = len(mistakes)
        mistake_count = np.sum(mistakes >= 1)
        p_mistake = float(mistake_count) / moves
        loss_total = np.sum(mistakes)
        loss_mean = loss_total / moves
        loss_std_dev = np.std(losses)

        accuracy = player_rows['Search'].sum() / player_rows['Best Search'].sum()
        best_move = player_rows['Counts as Best'].mean()
        match = player_rows['Counts as Match'].mean()

        statistics[key] = {
            'moves': moves,
            'mistakes': mistake_count,
            'p(mistake)': p_mistake,
            'loss_total': int(loss_total),
            'loss_mean': loss_mean,
            'loss_std_dev': loss_std_dev,
            'timeline': mistakes,
            'accuracy': accuracy,
            'best_move': best_move,
            'match': match,
        }

    return statistics


if __name__ == '__main__':
    target = sys.argv[1]
    if os.path.isfile(target):
        run(target)
    else:
        print(f'ERROR! Received a path that does not exist: {target}')
    pass
