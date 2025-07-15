from typing import List, Dict, Optional

import numpy as np

from composeanalysis.convert_to_policy_map import convert_to_policy_map
from composeanalysis.handle_symmetries_in_search import handle_symmetries_in_search
from composeanalysis.get_human_policies import get_human_policies
from composeanalysis.index_to_coordinate_label import index_to_coordinate_label
from composeanalysis.simplify_human_profile import simplify_human_profile
from katago import HumanProfile, Engine
from katago.response import SuccessResponse
from composeanalysis.get_search_responses import get_search_responses

def compose_analysis(
    engine: Engine,
    position_count: int,
    start: float,
    sgf: List[Dict],
    configuration: Dict,
    query_ids: Dict[Optional[HumanProfile], str]
) -> List[Dict]:
    root = sgf[0]
    size = int(root['SZ'] if 'SZ' in root else 19)

    print('Getting all search responses...')
    search_responses: List[SuccessResponse] = get_search_responses(engine, query_ids[None], position_count, start)

    print('All search responses received.  Getting human priors...')
    turn_to_profile_to_policy = get_human_policies(engine, query_ids, position_count, size)

    print('All human priors responses received.  Composing the analysis...')
    lead_drop = configuration['accuracy']['lead_drop']
    max_visit_ratio = configuration['accuracy']['max_visit_ratio']
    top_moves = configuration['accuracy']['top_moves']
    winrate_drop = configuration['accuracy']['winrate_drop']

    analysis: List[Dict] = []
    next_response = search_responses[-1]
    turn_number = next_response.turn_number
    posterior_lead = -next_response.move_infos[0].score_lead
    posterior_win_rate = 1. - next_response.move_infos[0].winrate
    for i in range(position_count - 2, -1, -1):
        # Get the current position's analysis and human policy priors.
        current_response = search_responses[i]
        current_policies = turn_to_profile_to_policy[i]

        # Extract the straightforward fields.
        player = current_response.root_info.current_player.value
        prior_lead = current_response.move_infos[0].score_lead
        prior_win_rate = current_response.move_infos[0].winrate

        favorite = current_response.move_infos[0].move.value
        played = sgf[i + 1][player]
        if not played:
            played = 'pass'

        # Process the search response's MoveInfos to handle symmetries.
        kept_infos, move_to_info, symmetries = handle_symmetries_in_search(current_response.move_infos)
        if played not in symmetries:
            symmetries[played] = {played}

        # Capture the visit counts necessary for calculating Accuracy and Best Match %.
        favorite_search = current_response.move_infos[0].visits
        threshold = np.floor(favorite_search * max_visit_ratio)
        played_search = 0 if played not in move_to_info else move_to_info[played].visits

        # If the player played a symmetry of the favorite move, this counts as a best and match move.  Simultaneously
        # correct the prior lead and win rate to account for the note below.
        #
        # Developer's Note: (J. Craig, 2022-01-12)
        # Adding logic to track how each player's moves compared with the best move and policy favorite revealed that
        # KG's score estimation can be further off than I thought.  If the player plays the AI's best move, the move should
        # never be considered a mistake.  That position's score needs to be pushed to the previous move as the expected
        # result.
        if played in symmetries[favorite]:
            counts_as_best = 1
            counts_as_match = 1
            prior_lead = posterior_lead
            prior_win_rate = posterior_win_rate

        # I expand the common definition of a "best" move to include moves that do not deviate too far from the favorite
        # move's results.  This means that moves that KataGo did not consider yet do as well as the favorite move will
        # count as both a best and match move.
        elif prior_lead - posterior_lead < lead_drop and prior_win_rate - posterior_win_rate < winrate_drop:
            counts_as_best = 1
            counts_as_match = 1

        # Otherwise, the move does not count as a "best" move.  It may still count as a match.
        else:
            counts_as_best = 0

            # We need to find the moves that KataGo would treat as matches.  These are the top N moves that have enough
            # visits for the results to be considered somewhat reliable.
            counts_as_match = 0
            for j in range(1, top_moves):
                candidate = kept_infos[j]
                if candidate.visits < threshold:
                    break

                if (
                    candidate.move in symmetries[played] or
                    candidate.score_lead - posterior_lead < lead_drop and
                    candidate.winrate - posterior_win_rate < winrate_drop
                ):
                    counts_as_match = 1
                    break

        # Calculate KG's expected loss.
        expected_loss = 0.
        seen = kept_infos[0].prior
        for mi in kept_infos[1:]:
            move_loss = prior_lead - mi.score_lead
            move_prior = mi.prior
            expected_loss += move_loss * move_prior
            seen += move_prior
        expected_loss /= seen

        # Create a simplified version of the search response to include in the output CSV.
        search = {
            'turnNumber': turn_number,
            'rootInfo': {
                'currentPlayer': player,
                'visits': current_response.root_info.visits,
            },
            'policy': current_response.policy,
            'ownership': {index_to_coordinate_label(j, size): v for j, v in enumerate(current_response.ownership)},
            'moveInfos': [
                {
                    'isSymmetryOf': x.is_symmetry_of,
                    'move': x.move.value,
                    'order': x.order,
                    'prior': x.prior,
                    'scoreLead': x.score_lead,
                    'visits': x.visits,
                    'winrate': x.winrate,
                } for x in current_response.move_infos
            ]
        }

        # Iterate through the human profiles.  Use the findings to build the expected priors and policies objects.
        policies: Dict[str, Dict[str, float]] = {}
        priors: Dict[str, float] = {}
        for hp in HumanProfile:
            if hp not in current_policies:
                continue
            label = simplify_human_profile(hp)
            policies[label] = current_policies[hp]
            priors[label] = current_policies[hp][played]

        # Add the Random prior and policy.
        legal_move_count = sum(1 for x in current_response.policy if x > -0.5)
        random_prior = 1. / legal_move_count
        priors['random'] = random_prior
        policies['random'] = {x: random_prior for x in current_policies[HumanProfile.RANK_20K]}

        # Add the AI prior and policy.
        ai_policy = convert_to_policy_map(size, current_response.policy)
        policies['AI'] = ai_policy
        priors['AI'] = ai_policy[played]

        # Build and save the analysis row.
        analysis_row = {
            'move': turn_number,
            'player': player,
            'prior lead': prior_lead,
            'posterior lead': posterior_lead,
            'loss': prior_lead - posterior_lead,
            'prior win rate': prior_win_rate,
            'posterior win rate': posterior_win_rate,
            'drop': prior_win_rate - posterior_win_rate,
            'played': played,
            'best': favorite,
            'played search': played_search,
            'best search': favorite_search,
            'counts as best': counts_as_best,
            'counts as match': counts_as_match,
            'expected loss': expected_loss,
            'priors': priors,
            'policies': policies,
            'search': search,
        }
        analysis.insert(0, analysis_row)

        # Prepare for the next iteration using the corrected values.
        next_response = current_response
        turn_number = current_response.turn_number
        posterior_lead = -prior_lead
        posterior_win_rate = 1. - prior_win_rate

    print('Analysis composed.')
    return analysis
