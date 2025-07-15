import os
import re
import sys
from collections import OrderedDict, Counter
from typing import Any

import jsons
import numpy as np
import pandas as pd

from damage import calculate_damage
from domain.coordinate import Coordinate
from domain.game import Game
from domain.pass_enum import Pass
from domain.ruleset import Ruleset
from go_study import ratings, _1d, Statistics
from main import load_configuration, ScoringProcedure, get_or_create_analysis_file, load_sgf, prep_katago, get_komi


def translate_json_field(raw: str) -> Any:
    unescaped = raw.replace('""', '"')
    return jsons.loads(unescaped)


def calculate_expected_loss(row):
    # This is how the calculation should work in the GPQ analysis core itself.  I will fix it soon.
    search = row['Parsed']
    favorite_lead = search['moveInfos'][0]['scoreLead']

    expected_loss = 0.
    overall_likelihood = 0.
    for mi in search['moveInfos']:
        loss = favorite_lead - mi['scoreLead']
        prior = mi['prior']
        expected_loss += loss * prior
        overall_likelihood += prior
    expected_loss /= overall_likelihood

    return expected_loss


loss_bins = OrderedDict()
loss_bins['<0.5'] = lambda loss: loss < 0.5
loss_bins['≥0.5'] = lambda loss: 0.5 <= loss < 1.5
loss_bins['≥1.5'] = lambda loss: 1.5 <= loss < 3.0
loss_bins['≥3.0'] = lambda loss: 3.0 <= loss < 6.0
loss_bins['≥6.0'] = lambda loss: 6.0 <= loss < 12.0
loss_bins['≥12.0'] = lambda loss: 12.0 <= loss


def label_move(loss: float) -> str:
    for label, evaluator in loss_bins.items():
        if evaluator(loss):
            return label
    return '???'


def convert_sgf_rating_to_numerical_rating(source: str) -> float | None:
    if not source:
        return None

    lower = source.lower()
    if lower.endswith('p'):
        return 8.5

    match = re.match(r'(\d+)[dk]', lower)
    if not match:
        return None

    number = int(match.group(1))
    if number > 20:
        return -21.5  # Random

    return ratings.index(lower) - 21.5


configuration = load_configuration()
prep_katago(configuration['katago'])
procedure = ScoringProcedure(configuration['transformation_parameters'])
procedure.score(np.zeros((150,)))
calculate_damage(150, 0.5, 0.5, 0.5, 0.5)

def run(sgf_filename: str):
    # HACK: Transform the output to the desired directory.
    json_filename = sgf_filename[:-4] + '.json'
    json_filename = json_filename.replace('sgf', 'json')
    json_filename = re.sub('(?:ranked|free)[\\\\/]', '', json_filename)
    print(json_filename)
    os.makedirs(
        json_filename[:json_filename.rindex('\\')],
        exist_ok=True
    )

    game, black_name, white_name, size, winner = load_sgf(sgf_filename)
    root = game[0]

    # Fix some fields that Fox screws up.
    for rank in ('BR', 'WR'):
        if rank in root:
            found = root[rank]
            found = found.replace('段', 'd')
            found = found.replace('级', 'k')
            found = found.replace(r'\+', '')
            root[rank] = found

    ruleset = Ruleset[root['RU'].upper() if 'RU' in root else 'CHINESE']
    root['KM'] = get_komi(root, ruleset)

    analysis_filename = get_or_create_analysis_file(sgf_filename, configuration, game)

    df = pd.read_csv(analysis_filename)
    df['Parsed'] = df.apply(lambda row: translate_json_field(row['Search']), axis=1)
    df['Corrected Expected Loss'] = df.apply(calculate_expected_loss, axis=1)

    breakdowns = OrderedDict()
    simplicities = OrderedDict()
    for view in ('Overall', 'Opening', 'Middle', 'End'):
        breakdown = OrderedDict()
        simplicity = OrderedDict()
        for player in ('B', 'W'):
            breakdown[player] = Counter()
            simplicity[player] = Counter()
        breakdowns[view] = breakdown
        simplicities[view] = simplicity

    performances_by_player_stage = OrderedDict()
    for player in ('black', 'white'):
        performances_by_stage = OrderedDict()
        for view in ('overall', 'opening', 'middle', 'end'):
            performances_by_stage[view] = OrderedDict()
        performances_by_player_stage[player] = performances_by_stage

    for _, row in df.iterrows():
        mi = row['Move']
        player = row['Player']
        loss = row['Loss']
        drop = row['Drop']
        quality = label_move(loss)

        # expected_loss_series = player_subset['Corrected Expected Loss'].to_numpy()
        # simplicity_score = procedure.score(expected_loss_series)[0]
        expected_loss = row['Corrected Expected Loss']
        expected_quality = label_move(expected_loss)

        breakdowns['Overall'][player][quality] += 1
        simplicities['Overall'][player][expected_quality] += 1

        if mi < 51:
            stage = 'Opening'
        elif mi < 151:
            stage = 'Middle'
        else:
            stage = 'End'
        breakdowns[stage][player][quality] += 1
        simplicities[stage][player][expected_quality] += 1

    for stage, breakdown in breakdowns.items():
        print(f'{stage}:')
        simplicity = simplicities[stage]

        if stage == 'Overall':
            subset = df
        elif stage == 'Opening':
            subset = df[df['Move'] < 51]
        elif stage == 'Middle':
            subset = df[np.logical_and(df['Move'] >= 51, df['Move'] < 151)]
        else:
            subset = df[df['Move'] >= 151]

        metrics = {'B': OrderedDict(), 'W': OrderedDict()}
        for player in ('B', 'W'):
            player_subset = subset[subset['Player'] == player]
            if len(player_subset) == 0:
                metrics[player]['Accuracy'] = np.nan
                metrics[player]['Best Move %'] = np.nan
                metrics[player]['Match %'] = np.nan
                metrics[player]['Drop Mean'] = np.nan
                metrics[player]['Loss Mean'] = np.nan
                metrics[player]['Quality Score'] = np.nan
                metrics[player]['Simplicity Score'] = np.nan
                metrics[player]['Rating'] = 'N/A'
                metrics[player]['Rating Range'] = None

                full_player = 'black' if player == 'B' else 'white'
                performances_stage = stage.lower()
                entry = performances_by_player_stage[full_player][performances_stage]
                entry['accuracy'] = np.nan
                entry['bestMove'] = np.nan
                entry['match'] = np.nan
                entry['dropMean'] = np.nan
                entry['lossMean'] = np.nan
                entry['qualityScore'] = np.nan
                entry['simplicityScore'] = np.nan
                entry['probableRating'] = np.nan
                entry['probableRatingLabel'] = np.nan
                entry['ratingMean'] = np.nan
                entry['ratingStdDev'] = np.nan
                entry['ratingRangeLabel'] = np.nan
                entry['actualLosses'] = {k: np.nan for k in loss_bins}
                entry['expectedLosses'] = {k: np.nan for k in loss_bins}

                continue

            visit_correction = player_subset[['Played Search', 'Best Search']].min(axis=1)
            accuracy = 100 * visit_correction.sum() / player_subset['Best Search'].sum()
            best_move = 100 * player_subset['Counts as Best'].sum() / len(player_subset)
            match = 100 * player_subset['Counts as Match'].sum () / len(player_subset)
            drop_mean = 100 * player_subset['Drop'].sum() / len(player_subset)
            loss_mean = player_subset['Loss'].sum() / len(player_subset)

            loss_series = player_subset['Loss'].to_numpy()
            quality_score = procedure.score(loss_series)[0]

            # WARNING: The calculation of Expected Loss is currently inaccurate.  This needs to be fixed in GPQ's analysis
            # core.
            expected_loss_series = player_subset['Corrected Expected Loss'].to_numpy()
            simplicity_score = procedure.score(expected_loss_series)[0]

            player_ratings = player_subset[ratings]
            natural_log = np.log(player_ratings)
            sums = natural_log.sum(axis=0)
            offset = np.max(sums)
            normalized = sums - offset
            product = np.exp(normalized)
            denominator = product.sum()
            probabilities = product / denominator

            mlr = 'Random'
            most_likely_rating = 'Random'
            most_likely_rating_likelihood = -1.
            mean = 0.
            for i, r in enumerate(ratings):
                r_i = i - _1d - 0.5
                likelihood = probabilities[r]
                mean += r_i * likelihood

                if likelihood >= most_likely_rating_likelihood:
                    most_likely_rating_likelihood = likelihood
                    most_likely_rating = f'{r} ({likelihood*100:.2f}%)'
                    mlr = r

            variance = 0.
            for i, r in enumerate(ratings):
                r_i = i - _1d - 0.5
                likelihood = probabilities[r]
                variance += likelihood * (r_i - mean) ** 2
            standard_deviation = np.sqrt(variance)

            statistics = Statistics(mean, standard_deviation)

            # Put everything together for the display.
            metrics[player]['Accuracy'] = accuracy
            metrics[player]['Best Move %'] = best_move
            metrics[player]['Match %'] = match
            metrics[player]['Drop Mean'] = drop_mean
            metrics[player]['Loss Mean'] = loss_mean
            metrics[player]['Quality Score'] = quality_score
            metrics[player]['Simplicity Score'] = simplicity_score
            metrics[player]['Rating'] = most_likely_rating
            metrics[player]['Rating Range'] = statistics

            full_player = 'black' if player == 'B' else 'white'
            performances_stage = stage.lower()
            entry = performances_by_player_stage[full_player][performances_stage]
            entry['accuracy'] = accuracy
            entry['bestMove'] = best_move
            entry['match'] = match
            entry['dropMean'] = drop_mean
            entry['lossMean'] = loss_mean
            entry['qualityScore'] = quality_score
            entry['simplicityScore'] = simplicity_score
            entry['probableRating'] = ratings.index(mlr) - 21.5
            entry['probableRatingLabel'] = mlr
            entry['ratingMean'] = statistics.mean
            entry['ratingStdDev'] = statistics.std
            entry['ratingRangeLabel'] = statistics.label
            entry['actualLosses'] = {k: breakdowns[stage][player][k] for k in loss_bins}
            entry['expectedLosses'] = {k: simplicities[stage][player][k] for k in loss_bins}

        separator = '|------------------|----------------------|----------------------|'
        brr = 'N/A' if not metrics["B"]["Rating Range"] else metrics["B"]["Rating Range"].label
        wrr = 'N/A' if not metrics["W"]["Rating Range"] else metrics["W"]["Rating Range"].label
        print('| Metric           | Black                | White                |')
        print(separator)
        print(f'| Probable Rating  | {metrics["B"]["Rating"]:20s} | {metrics["W"]["Rating"]:20s} |')
        print(f'| Rating Range     | {brr:20s} | {wrr:20s} |')
        print(f'| Accuracy         | {metrics["B"]["Accuracy"]:19.2f}% | {metrics["W"]["Accuracy"]:19.2f}% |')
        print(f'| Best Move %      | {metrics["B"]["Best Move %"]:19.2f}% | {metrics["W"]["Best Move %"]:19.2f}% |')
        print(f'| Match %          | {metrics["B"]["Match %"]:19.2f}% | {metrics["W"]["Match %"]:19.2f}% |')
        print(f'| Drop Mean        | {metrics["B"]["Drop Mean"]:19.2f}% | {metrics["W"]["Drop Mean"]:19.2f}% |')
        print(f'| Loss Mean        | {metrics["B"]["Loss Mean"]:19.2f}  | {metrics["W"]["Loss Mean"]:19.2f}  |')
        print(f'| Quality Score    | {metrics["B"]["Quality Score"]:19.2f}  | {metrics["W"]["Quality Score"]:19.2f}  |')
        print(f'| Simplicity Score | {metrics["B"]["Simplicity Score"]:19.2f}  | {metrics["W"]["Simplicity Score"]:19.2f}  |')

        print(separator)
        for loss_level in loss_bins.keys():
            black_entry = f'{breakdown["B"][loss_level]} ({simplicity["B"][loss_level]: >3})'
            white_entry = f'{breakdown["W"][loss_level]} ({simplicity["W"][loss_level]: >3})'
            print(f'| {loss_level: <16} | {black_entry: >20} | {white_entry: >20} |')

        print()

    # WARNING: I may need to expand this
    if 'RE' in root and len(root['RE']) > 2:
        kind = root['RE'][2:]
        if kind.startswith('R'):
            win_type = 'resignation'
        elif kind.startswith('T') or kind == '0.2':
            win_type = 'time'
        elif kind.startswith('F'):
            win_type = 'forfeit'
        elif re.match(r'^\d+(?:\.\d+)?$', kind):
            win_type = 'count'
        else:
            win_type = '?'
    else:
        win_type = '?'

    last_row = df.iloc[len(df) - 1]
    evaluation = last_row['Posterior Lead']
    if last_row['Player'] == 'W':
        evaluation *= -1

    state = Game(
        ruleset=ruleset,
        komi=root['KM'],
        handicap_stones=root['AB'] if 'AB' in root else None,
    )

    moves = []
    for _, row in df.iterrows():
        i = row['Move']
        moveName = row['Played']
        if moveName.lower() == 'pass':
            move = Pass.PASS
        else:
            move = Coordinate[moveName]
        state = state.play(move)

        # Calculate the move's Accuracy.
        favorite_visits = row['Best Search']
        played_visits = row['Played Search']
        accuracy = min(favorite_visits, played_visits) / favorite_visits * 100.

        # Calculate the move's Damage.
        damage, _, pwin = calculate_damage(
            i,
            row['Prior Lead'],
            row['Posterior Lead'],
            row['Prior Win Rate'],
            row['Posterior Win Rate'],
        )

        # Calculate some expected values to use for exploring sharpness, simplicity, and other ideas.
        expected_damage = 0.
        expected_drop = 0.
        expected_p_win = 0.
        expected_win_rate = 0.
        favorite_win_rate = row['Prior Win Rate']
        seen = 0.
        for mi in row['Parsed']['moveInfos']:
            likelihood = mi['prior']
            win_rate = mi['winrate']
            drop = favorite_win_rate - win_rate

            d, _, apwin = calculate_damage(
                i,
                row['Prior Lead'],
                mi['scoreLead'],
                row['Prior Win Rate'],
                win_rate
            )
            apwin /= 100.  # we will rescale it later

            expected_damage += d * likelihood
            expected_drop += drop * likelihood
            expected_p_win += apwin * likelihood
            expected_win_rate += win_rate * likelihood
            seen += likelihood

        expected_damage /= seen
        expected_drop = 100 * expected_drop / seen
        expected_p_win = 100 * expected_p_win / seen
        expected_win_rate = 100 * expected_win_rate / seen

        # Extract the Rating policy information for the move so we can calculate overall performance ratings later.
        priors = {r: row[f'{r}'] for r in ratings}

        move = {
            'index': row['Move'],
            'player': row['Player'],
            'move': moveName,
            'priorLead': row['Prior Lead'],
            'posteriorLead': row['Posterior Lead'],
            'loss': row['Loss'],
            'priorWinRate': row['Prior Win Rate'] * 100.,
            'posteriorWinRate': row['Posterior Win Rate'] * 100.,
            'drop': row['Drop'] * 100.,
            'favorite': row['Best'],
            'playedVisits': played_visits,
            'favoriteVisits': favorite_visits,
            'accuracy': accuracy,
            'countsAsBest': row['Counts as Best'],
            'countsAsMatch': row['Counts as Match'],
            'expectedLoss': row['Corrected Expected Loss'],
            'captured': state.stones_captured_last_turn,
            'koCapture': 1 if state.previous_turn_captured_ko else 0,
            'kos': state.kos,  # debug
            'koComplete': 1 if state.previous_turn_ended_ko else 0,
            'damage': damage,
            'pWin': pwin,
            'expectedDamage': expected_damage,
            'expectedDrop': expected_drop,
            'expectedPWin': expected_p_win,
            'expectedWinRate': expected_win_rate,
            'priors': priors,
        }
        moves.append(move)

    if 'OT' in root:
        overtime = root['OT']
    elif 'TC' in root and 'TT' in root:  # gorram Fox
        overtime = f'{root["TC"]}x{root["TT"]} seconds byo-yomi'
    else:
        overtime = None
    report = {
        'source': sgf_filename,
        'name': root['GN'] if 'GN' in root else None,
        'players': {
            'black': {
                'name': black_name,
                'rating': convert_sgf_rating_to_numerical_rating(root['BR']) if 'BR' in root else None,
                'sourceRating': root['BR'] if 'BR' in root else '?',
                'team': root['BT'] if 'BT' in root else None,
            },
            'white': {
                'name': white_name,
                'rating': convert_sgf_rating_to_numerical_rating(root['WR']) if 'WR' in root else None,
                'sourceRating': root['WR'] if 'WR' in root else '?',
                'team': root['WT'] if 'WT' in root else None,
            },
        },
        'setup': {
            'size': root['SZ'],
            'ruleset': root['RU'] if 'RU' in root else 'Chinese',  # cuz Fox
            'handicap': root['HA'] if 'HA' in root else 0,
            'komi': root['KM'],
            'mainTime': root['TM'] if 'TM' in root else None,
            'overtime': overtime,
            'startingBlack': root['AB'] if 'AB' in root else None,
            'startingWhite': root['AW'] if 'AW' in root else None,
        },
        'history': {
            'date': root['DT'] if 'DT' in root else None,
            'event': root['EV'] if 'EV' in root else None,
            'place': root['PC'] if 'PC' in root else None,
            'round': root['RO'] if 'RO' in root else None,
        },
        'result': {
            'winner': winner,
            'by': win_type,
            'evaluation': evaluation,
        },
        'performances': performances_by_player_stage,
        'moves': moves
    }

    report = jsons.dumps(report, jdkwargs={'ensure_ascii': False, 'indent': 2})

    with open(json_filename, 'w', encoding='UTF-8') as outfile:
        outfile.write(report)


if __name__ == '__main__':
    run(sys.argv[1])
