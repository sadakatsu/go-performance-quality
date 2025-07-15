import functools
import re
from collections import OrderedDict, Counter

import jsons
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, List, Tuple, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from damage import calculate_damage
from katago import Engine
from main import load_configuration, prep_katago, load_sgf, get_or_create_analysis_file
from parse import parse_sgf_contents
from plot import _set_matplotlib_fonts

get_katago: Optional[Callable[[], Engine]] = None
katago: Optional[Engine] = None

ratings = [
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
    'AI'
]
policies = [
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
    'AI Policy'
]
all_columns = [*ratings]
all_columns.insert(0, 'Player')

_20k = ratings.index('20k')
_1d = ratings.index('1d')
_pro = ratings.index('Pro')
_ai = ratings.index('AI')

rating_map = {r: i - _1d - 0.5 for i, r in enumerate(ratings)}
rating_values = pd.DataFrame([i - _1d - 0.5 for i, _ in enumerate(ratings)], ratings)

move_pattern = re.compile(r'(?i)pass|[ABCDEFGHJKLMNOPQRST]\d{1,2}')
standard_column = 'ABCDEFGHJKLMNOPQRST'
sgf_coordinate =  'abcdefghijklmnopqrs'

loss_levels = OrderedDict()
loss_levels['Incredible'] = 'Loss ≤ -0.05, Drop ≤ 0'
loss_levels['Gain'] = 'Loss ≤ -0.05, Drop > 0'
loss_levels['Optimal'] = '-0.05 < Loss < 0.05'
loss_levels['Excellent'] = '0.05 ≤ Loss < 0.25'
loss_levels['Good'] =  '0.25 ≤ Loss < 0.5'
loss_levels['Fair'] = '0.5 ≤ Loss < 0.75'
loss_levels['Inefficient'] = '0.75 ≤ Loss < 1'
loss_levels['Inaccurate'] = '1 ≤ Loss < 2'
loss_levels['Small Mistake'] = '2 ≤ Loss < 3'
loss_levels['Mistake'] = '3 ≤ Loss < 5'
loss_levels['Big Mistake'] = '5 ≤ Loss < 8'
loss_levels['Blunder'] = '8 ≤ Loss < 13'
loss_levels['Big Blunder'] = '13 ≤ Loss < 24'
loss_levels['Catastrophe'] = 'Loss ≥ 24'

@dataclass
class Commentary:
    i: int
    player: str
    worse_than_par: bool
    blocks_improvement: bool
    difficult: bool
    relative_loss: float
    heading: str
    comment: str
    favorite: str
    favorite_label: str
    recommendations: list[str]


@dataclass
class Range:
    start: float
    end: float

    @property
    def span(self) -> float:
        return self.end - self.start


@dataclass
class Statistics:
    mean: float
    std: float

    _ranges: Dict[int, Range] = field(default_factory=dict)

    @property
    def level(self) -> str:
        _, i = math.modf(self.mean)
        offset = 21 if self.mean < 0 else 22
        return ratings[int(i) + offset]

    @property
    def top(self) -> str:
        _, i = math.modf(self.mean + 3 * self.std)
        offset = 21 if self.mean < 0 else 22
        try:
            return ratings[int(i) + offset]
        except IndexError:
            return ratings[0] if self.mean < 0 else ratings[-1]

    @property
    def label(self) -> str:
        if self.mean < -1:
            estimated = np.round(-self.mean, 2)
            result = f'{estimated:0.2f}k'
            if self.mean <= -21:
                result = f'Random (~{result})'
        else:
            estimated = np.round(self.mean + 2, 2)
            result = f'{estimated:0.2f}d'
            if 8 <= self.mean < 9:
                result = f'pro (~{result})'
            elif self.mean >= 9:
                result = f'AI (~{result})'

        return result + f' ± {self.std:0.2f}'


def interpret(row):
    for column in row.index:
        read = row[column]
        x = jsons.loads(read, dict)
        row[column] = x
    return row


def process_row(row):
    rating_subset = row[ratings]
    policy_subset = interpret(row[policies])

    likelihoods = [rating_subset[r] for r in ratings]
    max_likelihoods = [None if r == 'Random' else max((policy_subset[r + ' Policy']).values()) for r in ratings]
    accuracies = [None if m is None else l / m for l, m in zip(likelihoods, max_likelihoods)]

    total = row[ratings].sum()
    normalized = (rating_subset / total).values.tolist()

    data = {
        'Rating': ratings,
        'Likelihood': likelihoods,
        'MaxLikelihood': max_likelihoods,
        'Accuracy': accuracies,
        'Posterior Probability': normalized,
    }
    row_df = pd.DataFrame(data)
    row_df.set_index('Rating', inplace=True)

    return row_df


def standard_to_sgf(standard):
    if standard.lower() == 'pass':
        return ''

    column_index = standard_column.index(standard[0])
    sgf_column = sgf_coordinate[column_index]

    standard_row = int(standard[1:])
    sgf_row_index = 19 - standard_row
    sgf_row = sgf_coordinate[sgf_row_index]

    return f'{sgf_column}{sgf_row}'


def consolidate_ratings(rating_pairs: List[Tuple[float, str]]) -> str:
    def reducer(result, current):
        index, label = current
        if not result:
            result = [[current]]
        else:
            previous_range = result[-1]
            previous_index, previous_label = previous_range[-1]
            if index - previous_index < 1.5:
                if len(previous_range) > 1:
                    previous_range.pop()
                previous_range.append(current)
            else:
                result.append([current])
        return result

    grouped = functools.reduce(reducer, rating_pairs, [])
    return ', '.join([f'{"-".join([p[1] for p in g])}' for g in grouped])


def label_move(loss: float, drop: float) -> str:
    if loss <= -0.05:
        quality = 'Incredible' if drop <= 0. else 'Gain'
    elif loss < 0.05:
        quality = 'Optimal'
    elif loss < 0.25:
        quality = 'Excellent'
    elif loss < 0.5:
        quality = 'Good'
    elif loss < 0.75:
        quality = 'Fair'
    elif loss < 1.:
        quality = 'Inefficient'
    elif loss < 2.:
        quality = 'Inaccurate'
    elif loss < 3.:
        quality = 'Small Mistake'
    elif loss < 5.:
        quality = 'Mistake'
    elif loss < 8.:
        quality = 'Big Mistake'
    elif loss < 13.:
        quality = 'Blunder'
    elif loss < 24:
        quality = 'Big Blunder'
    else:
        quality = 'Catastrophic'
    return quality


def label_likelihood(likelihood: float) -> str:
    if likelihood >= 99.:
        likelihood_descriptor = 'Obvious'
    elif likelihood >= 85.:
        likelihood_descriptor = 'Regular'
    elif likelihood >= 71.:
        likelihood_descriptor = 'Common'
    elif likelihood >= 57.:
        likelihood_descriptor = 'Likely'
    elif likelihood >= 43.:
        likelihood_descriptor = 'Probable'
    elif likelihood >= 29.:
        likelihood_descriptor = 'Occasional'
    elif likelihood >= 15.:
        likelihood_descriptor = 'Uncommon'
    elif likelihood >= 1.:
        likelihood_descriptor = 'Rare'
    else:
        likelihood_descriptor = 'Anomalous'
    return likelihood_descriptor


def save_sgf(sgf: List[Dict[str, Any]], original_sgf_filename: str, suffix: str) -> str:
    constructed_sgf = '('
    for node in sgf:
        constructed_sgf += ';'
        for key, value in node.items():
            constructed_sgf += key
            if type(value) is list:
                if len(value) > 0:
                    converted = [
                        standard_to_sgf(x) if move_pattern.match(x) else re.sub(r'([\]\\:])', r'\\\1', str(x))
                        for x in value
                    ]


                    constructed_sgf += ''.join(f'[{x}]' for x in converted)
            else:
                if type(value) is str:
                    if move_pattern.match(value):
                        representation = standard_to_sgf(value)
                    else:
                        representation = re.sub(r'([\]\\:])', r'\\\1', value)
                else:
                    representation = str(value)

                constructed_sgf += f'[{representation}]'
    constructed_sgf += ')'

    annotated_filename = f'{original_sgf_filename[:-4]}_{suffix}.sgf'
    with open(annotated_filename, 'w', encoding='UTF-8') as outfile:
        outfile.write(constructed_sgf)

    return annotated_filename

def run(sgf_filename: str, subject: Optional[str], n: int):
    global katago

    # Run the GPQ process to generate the analysis file if it does not exist.
    configuration = load_configuration()
    prep_katago(configuration['katago'])
    game, black_name, white_name, size, winner = load_sgf(sgf_filename)
    analysis_filename = get_or_create_analysis_file(sgf_filename, configuration, game)

    # Determine the player of interest.
    player_of_interest = 'both'
    if subject is not None:
        if subject == black_name or subject == 'B':
            player_of_interest = 'B'
            print(f'Reviewing for Black ({black_name}).')
        elif subject == white_name or subject == 'W':
            player_of_interest = 'W'
            print(f'Reviewing for White ({white_name}).')
        else:
            print('Unrecognized subject, reviewing for both players.')
    else:
        print('No subject specified, reviewing for both players.')

    # Load the analysis file.
    print('Reading analysis file...')
    df = pd.read_csv(analysis_filename)
    rating_df = df[all_columns]

    # Load the SGF.
    print('Reading SGF...')
    with open(sgf_filename) as infile:
        contents = infile.read()
    sgf = parse_sgf_contents(contents)

    # Figure out each player's rating probabilities.
    print('Evaluating player performance ratings...')
    player_stats = {}
    player_rating_probabilities = {}
    for player in ('B', 'W'):
        player_subset = rating_df[rating_df['Player'] == player][ratings]
        natural_log = np.log(player_subset)
        sums = natural_log.sum(axis=0)
        offset = np.max(sums)
        normalized = sums - offset
        product = np.exp(normalized)
        denominator = product.sum()
        probabilities = product / denominator

        player_rating_probabilities[player] = probabilities

        mean = 0.
        for i, r in enumerate(ratings):
            r_i = i - _1d - 0.5
            likelihood = probabilities[r]
            mean += r_i * likelihood

        variance = 0.
        for i, r in enumerate(ratings):
            r_i = i - _1d - 0.5
            likelihood = probabilities[r]
            variance += likelihood * (r_i - mean) ** 2
        standard_deviation = np.sqrt(variance)

        statistics = Statistics(mean, standard_deviation)
        player_stats[player] = statistics

        # HACK: It seems that giving Black a handicap artificially boosts his rating (as exemplified by a single game).
        # Subtract the handicap stones given from Black's mean rating.  Don't let the rating drop below random, though.
        if player == 'B' and 'HA' in sgf[0] and sgf[0]['HA'] > 1:
            statistics.mean -= sgf[0]['HA']
            if statistics.mean < -21:
                statistics.mean = -21

        print(f'- {black_name if player == "B" else white_name} ({player}): {statistics.label}')

    # Graph the player rating probabilities.
    print('Generating rating probability graph...')
    _set_matplotlib_fonts(analysis_filename)  # naughty, importing a private function... thpbbt!
    plt.close('all')
    figure, axis = plt.subplots()
    axis.set_title('Player Rating Probabilities')
    axis.set_ylabel('Probability')
    axis.set_xticks(np.arange(len(ratings)))
    axis.set_xticklabels(ratings, rotation=90, ha='center', va='top')
    axis.set_ylim(0., 1.)
    axis.grid(True, linewidth=0.5, zorder=0)

    axis.bar(
        np.arange(len(ratings)),
        player_rating_probabilities['B'],
        align='edge',
        width=-1. / 3.,
        label=f'{black_name} (Black)',
        zorder=3
    )
    axis.bar(
        np.arange(len(ratings)),
        player_rating_probabilities['W'],
        align='edge',
        width=1. / 3.,
        label=f'{white_name} (White)',
        zorder=3
    )

    figure.legend(loc='lower center', ncols=2)

    plt.tight_layout()
    figure.set_size_inches(8., 6.)
    graph_filename = sgf_filename[:-4] + '-rating-probabilities.png'
    plt.savefig(graph_filename, format='png', dpi=96)
    print(f'Graph saved to {graph_filename} .')

    # Review all the moves.  We want every move's comment so we can generate both a study file and a complete file.
    # Since it's convenient, we will add all the win rate and lead values to the SGF at the same time.
    print('Commenting all the moves...')
    move_assessments: List[Optional[Commentary]] = []
    player_breakdown = {'B': Counter(), 'W': Counter()}
    player_move_assessments: Dict[str, List[Commentary]] = {'B': [], 'W': []}
    for i, node in enumerate(sgf):
        # If this is the root node, handle only the V (value) and SBKV (Sabaki value) nodes for now.  The rest need to
        # be composed after processing the rest of the SGF.
        if i == 0:
            first_row = df.iloc[0]
            player = first_row['Player']
            win_rate = first_row['Prior Win Rate']
            lead = first_row['Prior Lead']
            black_lead = lead if player == 'B' else lead * -1.
            black_win_rate = win_rate if player == 'B' else 1. - win_rate
            node['SBKV'] = f'{100 * black_win_rate:0.2f}'
            node['V'] = f'{black_lead:+0.2f}'
            continue

        # Get the raw search stats from the row.
        row = df.iloc[i - 1]
        player = row['Player']
        played = row['Played']
        favorite = row['Best']
        search = jsons.loads(row['Search'])

        prior_lead = row['Prior Lead']
        posterior_lead = row['Posterior Lead']
        loss = row['Loss']

        prior_win_rate = row['Prior Win Rate']
        posterior_win_rate = row['Posterior Win Rate']
        drop = row['Drop']

        damage, prior_p_win, posterior_p_win = calculate_damage(
            move=row['Move'],
            prior_lead=prior_lead,
            posterior_lead=posterior_lead,
            prior_win_rate=prior_win_rate,
            posterior_win_rate=posterior_win_rate,
        )

        black_lead = posterior_lead * (1. if player == 'B' else -1.)
        black_win_rate = posterior_win_rate if player == 'B' else 1. - posterior_win_rate

        node['SBKV'] = f'{100 * black_win_rate:0.2f}'
        node['V'] = f'{black_lead:+0.2f}'

        # Label the move based upon its Loss.
        quality = label_move(loss, drop)
        current_breakdown = player_breakdown[row['Player']]
        current_breakdown.update([quality])

        # Determine the move's level in reference to the player's performance.
        player_statistics = player_stats[player]
        level = player_statistics.level
        if level == 'Random':
            level = '20k'  # correct so that beginners can at least start learning some sensible moves
        at_level_policy = jsons.loads(row[f'{level} Policy'])

        # Preprocess the moves using the isSymmetryOf field.
        symmetries = {}
        for mi in search['moveInfos']:
            move = mi['move']
            symmetry = mi['isSymmetryOf']
            if symmetry:
                symmetry_set = symmetries[symmetry]
                symmetry_set.add(move)
                symmetries[move] = symmetry_set
            else:
                symmetries[move] = {move}

        favorite_symmetries = symmetries[favorite]
        played_symmetries = {played} if played not in symmetries else symmetries[played]

        # Determine the at-level assessment data.
        at_level_likelihood = at_level_policy[played]

        at_level_better_likelihood = 0.
        at_level_single_better_likelihood = 0.
        expected_loss = 0.
        seen_likelihood = 0.
        for mi in search['moveInfos']:
            move = mi['move']
            if move.lower() == 'pass':
                move = 'pass'

            move_likelihood = at_level_policy[move]
            move_loss = prior_lead - mi['scoreLead']
            expected_loss += move_likelihood * move_loss

            seen_likelihood += move_likelihood

            if move in played_symmetries:
                continue

            if move_loss < loss - 0.05:  # we want some reason to believe the move is better
                at_level_better_likelihood += move_likelihood
                if move_likelihood > at_level_single_better_likelihood:
                    at_level_single_better_likelihood = move_likelihood

        expected_loss /= seen_likelihood  # normalize for the moves that were actually processed

        # Find the rating intervals that are most likely to have played this move.
        analysis_df = process_row(row)
        max_posterior_probability = analysis_df['Posterior Probability'].max()
        cutoff = min(1 / 32, max_posterior_probability - 0.005)
        most_likely_range_indices = analysis_df['Posterior Probability'] >= cutoff
        most_likely_range = analysis_df[most_likely_range_indices]
        most_likely_range_pairs = [(rating_map[r], r) for r in list(most_likely_range.index.values)]
        most_likely_range_groups = consolidate_ratings(most_likely_range_pairs)
        most_likely_ratings_set = set(most_likely_range.index.values)

        # Determine whether players above the player's top performance level are likely to play this move.
        top_of_range = player_statistics.top
        top_of_range_index = ratings.index(top_of_range)
        higher_ratings = {r for i, r in enumerate(ratings) if i > top_of_range_index}
        likely_higher_ratings = most_likely_ratings_set & higher_ratings

        # There are three flags I track for determining how important it is to review a move:
        # 1. Was this move worse than par?  By this I mean the player's Relative Loss (Actual Loss - Expected Loss) is
        #    greater than or equal to 0.75.
        # 2. Does this move block improvement?  By this I mean that the Actual Loss is >= 0.75 and ratings above this
        #    player's performance range are significantly less likely to play this move.
        # 3. Is this a difficult position?  By this I mean that players at the player's performance rating are expected
        #    to make at least a Small Mistake (Expected Loss >= 2.0).
        relative_loss = loss - expected_loss
        worse_than_par = relative_loss >= 0.75
        blocks_improvement = loss >= 0.75 and len(higher_ratings) > 0 and len(likely_higher_ratings) == 0
        difficult = expected_loss >= 2.

        # BUILD THE REVIEW COMMENT.  We need a comment for every position for the complete version.
        # Generate a heading based upon the combination of flags.
        if worse_than_par:
            if blocks_improvement:
                if difficult:
                    heading = '**STUDY THIS POSITION!**'
                else:
                    heading = '**WEAK MOVE BLOCKING GROWTH**'
            elif difficult:
                heading = '**MISSTEP IN DIFFICULT POSITION**'
            else:
                heading = '**MISSTEP**'
        elif blocks_improvement:
            if difficult:
                heading = '**DIFFICULT POSITION REQUIRING STRONGER MOVES**'
            else:
                heading = '**OPPORTUNITY TO LEVEL UP**'
        elif difficult:
            heading = '**CONSEQUENCE OF PREVIOUS CHOICES**'
        else:
            # heading = f'**{quality.upper()}, NOT AN ISSUE AT {level.upper()} LEVEL**'
            heading = f'**{quality.upper()}'
            if loss >= 0.75:
                heading += f', NOT AN ISSUE AT {level.upper()}'
            heading += '**'

        # Generate notes based upon the flags.
        notes = []
        if worse_than_par:
            notes.append(f'- Worse than expected at the {level} level')
        if blocks_improvement:
            notes.append(f'- Much less likely to be played above the {top_of_range} level')
        if difficult:
            notes.append(
                f'- Difficult position for {level} level; review past choices to see whether this might be the '
                f'consequence of earlier poor decisions'
            )

        # Label the Expected Loss.
        expected_loss_label = label_move(expected_loss, 0.01)  # We should not expect Incredible moves.

        # Describe the relative loss.
        if -0.05 < relative_loss < 0.05:
            relative_loss_description = 'Similar'
        else:
            kind = 'Better' if relative_loss < 0 else 'Worse'
            abs_loss = abs(relative_loss)
            if abs_loss < 0.25:
                scale = 'Minutely'
            elif abs_loss < 0.5:
                scale = 'Slightly'
            elif abs_loss < 0.75:
                scale = 'Moderately'
            elif abs_loss < 1:
                scale = ''
            elif abs_loss < 2:
                scale = 'Notably'
            elif abs_loss < 3:
                scale = 'Substantially'
            elif abs_loss < 5:
                scale = 'Much'
            elif abs_loss < 8:
                scale = 'Far'
            else:
                scale = 'Immensely'
            relative_loss_description = ' '.join(x for x in (scale, kind) if x)

        # Describe the various move likelihoods.
        move_likelihood_label = label_likelihood(100 * at_level_likelihood)
        at_level_single_better_likelihood_label = label_likelihood(100 * at_level_single_better_likelihood)
        at_level_better_likelihood_label = label_likelihood(100 * at_level_better_likelihood)

        # Pick up to the top three recommendations for the appropriate policy.
        favorite_label = '△'
        recommendation_labels = []
        if expected_loss < -0.05 or played not in symmetries[favorite]:
            if top_of_range != 'AI' and blocks_improvement and not (worse_than_par or difficult):
                recommendation_level = ratings[ratings.index(top_of_range) + 1]
            else:
                recommendation_level = level

            recommendation_policy = jsons.loads(row[f'{recommendation_level} Policy'])
            candidates = [
                (mi, recommendation_policy['pass' if mi['move'].lower() == 'pass' else mi['move']])
                for mi in search['moveInfos']
                if mi['move'] not in played_symmetries
                   and mi['isSymmetryOf'] is None
                   and prior_lead - mi['scoreLead'] < loss - 0.05
            ]
            candidates.sort(key=lambda x: x[1], reverse=True)
            candidates = candidates[:3]
            # node['LB'] = [f'{standard_to_sgf(c[0]["move"])}:{chr(65 + i)}' for i, c in enumerate(candidates)]
            recommendation_labels = [f'{standard_to_sgf(c[0]["move"])}:{chr(65 + i)}' for i, c in enumerate(candidates)]

            favorite_label = None
            recommendations = []
            for j, (mi, likelihood) in enumerate(candidates):
                label = chr(65 + j)
                if mi['move'] in symmetries[favorite]:
                    favorite_label = label
                recommendations.append(
                    f"- {mi['move']} ({label}) :: Loss {prior_lead - mi["scoreLead"]:0.2f}, Likelihood {100 * likelihood:0.2f}%"
                )

            if favorite_label is None:
                favorite_label = '△'

            if recommendations:
                recommendation = f'{recommendation_level} RECOMMENDATIONS:\n{'\n'.join(recommendations)}'
            else:
                recommendation = f'NO RECOMMENDATIONS:\n- There are no better {level} policy moves.  Wonderful!'

            recommendation += f'\n\nAI Favorite: {favorite} ({favorite_label}) :: Loss 0.00, Likelihood {100 * recommendation_policy[favorite]:0.2f}%'

        else:
            recommendation = f'NO RECOMMENDATIONS:\n- {player} played the engine\'s favorite move.  Good job!'

        # Collect the five most likely ratings to play the selected move.
        overall = [(r, analysis_df.loc[r]['Posterior Probability'], analysis_df.loc[r]['Likelihood']) for r in ratings]
        overall.sort(key=lambda r: r[1], reverse=True)

        # Build the comment.
        comment = f'{heading}\n\n'
        if worse_than_par or blocks_improvement or difficult:
            comment += f'WHY THIS MOVE?\n{'\n'.join(notes)}\n\n'
        comment += f'''{level} ASSESSMENT:
> Expected Loss: {expected_loss:0.2f} ({expected_loss_label})
> Actual Loss: {loss:0.2f} ({quality})
> Relative Loss: {relative_loss:0.2f} ({relative_loss_description})
>
> Played Move Likelihood: {100*at_level_likelihood:0.2f}% ({move_likelihood_label})
> Highest Better Move Likelihood: {100*at_level_single_better_likelihood:0.2f}% ({at_level_single_better_likelihood_label})
> Cumulative Better Move Likelihood: {100*at_level_better_likelihood:0.2f}% ({at_level_better_likelihood_label})

{recommendation}

---

SEARCH METRICS:
> Drop: {100*drop:0.2f} ({100*prior_win_rate:0.2f}% -> {100*posterior_win_rate:0.2f}%)
> Loss: {loss:0.2f} ({prior_lead:+0.2f} -> {posterior_lead:+0.2f})
> Accuracy: {100*min(row['Played Search']/row['Best Search'],1):0.2f}%
> Damage: {damage:0.2f} ({prior_p_win:0.2f}% -> {posterior_p_win:0.2f}%)

MOST LIKELY RATINGS (Range {most_likely_range_groups}):
1. {overall[0][0]}: {100*overall[0][2]:0.2f}% ({100*overall[0][1]:0.2f}%)
2. {overall[1][0]}: {100*overall[1][2]:0.2f}% ({100*overall[1][1]:0.2f}%)
3. {overall[2][0]}: {100*overall[2][2]:0.2f}% ({100*overall[2][1]:0.2f}%)
4. {overall[3][0]}: {100*overall[3][2]:0.2f}% ({100*overall[3][1]:0.2f}%)
5. {overall[4][0]}: {100*overall[4][2]:0.2f}% ({100*overall[4][1]:0.2f}%)
'''

        # Save the comment to be used later.
        # move_assessments: List[Tuple[int, str, bool, bool, bool, float, str]] = []
        # player_move_assessments: Dict[str, List[Tuple[int, str, bool, bool, bool, float, str]]] = {'B': [], 'W': ''}
        # entry = i, player, worse_than_par, blocks_improvement, difficult, relative_loss, heading, comment, favorite, favorite_label,
        entry = Commentary(
            i,
            player,
            worse_than_par,
            blocks_improvement,
            difficult,
            relative_loss,
            heading,
            comment,
            favorite,
            favorite_label,
            recommendation_labels
        )
        move_assessments.append(entry)

        if worse_than_par or blocks_improvement or difficult:
            player_move_assessments[player].append(entry)

    # Build and save the study SGF.  Filter to the selected review color, and keep only the top N most worthwhile
    # comments in the SGF file.
    print('Generating study SGF...')
    performance_comments = []
    for player in ('B', 'W'):
        # THIS MAY CHANGE QUICKLY BASED UPON EXPERIMENTATION.
        # Prefer moves that are:
        # 1. Worse than par.
        # 2. Blocking growth.
        # 3. Not difficult.
        # 4. High relative loss.
        moves_to_study = sorted(
            player_move_assessments[player],
            key=lambda m: (not m.worse_than_par, not m.blocks_improvement, m.difficult, -m.relative_loss)
        )[:n]
        moves_to_study.sort(key=lambda m: m.i)
        recommended_to_study = '\n'.join(
            f'> - Move #{x.i}: {x.heading[2:-2].title()}, Relative Loss {x.relative_loss:0.2f}' for x in moves_to_study
        )

        comment = f'''{player} Performance Level: {player_stats[player].label}\n'''
        if player_of_interest == 'both' or player_of_interest == player:
            comment += f'''> Recommended Study:
{recommended_to_study}
    '''

            for entry in moves_to_study:
                study_node = sgf[entry.i]
                study_node['C'] = entry.comment
                if entry.favorite_label == '△':
                    study_node['TR'] = entry.favorite
                if entry.recommendations:
                    study_node['LB'] = entry.recommendations
        else:
            comment += '> not reviewed'

        performance_comments.append(comment)

    root_node = sgf[0]
    root_node['CA'] = 'UTF-8'
    root_node['C'] = '\n\n'.join(performance_comments)

    study_filename = save_sgf(sgf, sgf_filename, 'study')
    print(f'Study SGF saved to {study_filename} .')

    # Build and save the complete commentary.
    print('Building complete commentary...')
    summary = ''
    for player in ('B', 'W'):
        distribution = player_breakdown[player]
        amount = distribution.total()
        summary += f'{player} Performance Level: {player_stats[player].label}\n{player} Distribution:\n'
        for k, v in loss_levels.items():
            summary += f'> {distribution[k]} — {k} ({v}) — {100 * distribution[k] / amount:0.1f}%\n'
        summary += '\n'
    sgf[0]['C'] = summary

    for entry in move_assessments:
        study_node = sgf[entry.i]
        study_node['C'] = entry.comment
        if entry.favorite_label == '△':
            study_node['TR'] = entry.favorite
        if entry.recommendations:
            study_node['LB'] = entry.recommendations
    complete_filename = save_sgf(sgf, sgf_filename, 'complete')
    print(f'Complete commentary SGF saved to {complete_filename} .')

if __name__ == '__main__':
    target = sys.argv[1]
    subject = None if len(sys.argv) < 3 else sys.argv[2]
    n = 3 if len(sys.argv) < 4 else int(sys.argv[3])
    if os.path.isfile(target):
        run(target, subject, n)
    else:
        print(f'ERROR! Received a path that does not exist: {target}')
