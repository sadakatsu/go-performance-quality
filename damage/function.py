from typing import Optional

import joblib
import pandas as pd

from estimator import LogisticRegressionEstimator

indices = ['Move', 'Prior Lead', 'Posterior Lead', 'Prior Win Rate', 'Posterior Win Rate', 'Drop']
trained_estimator: Optional[LogisticRegressionEstimator] = None

def calculate_damage(
    move: int,
    prior_lead: float,
    posterior_lead: float,
    prior_win_rate: float,
    posterior_win_rate: float
) -> (float, float, float):
    global trained_estimator
    if trained_estimator is None:
        trained_estimator = joblib.load('damage/lre.gz')

    drop = prior_win_rate - posterior_win_rate
    expected = pd.Series(
        data={
            'Move': move,
            'Prior Lead': prior_lead,
            'Posterior Lead': prior_lead,
            'Prior Win Rate': prior_win_rate,
            'Posterior Win Rate': prior_win_rate,
            'Drop': 0.,
        },
        index=indices,
    )
    actual = pd.Series(
        data={
            'Move': move,
            'Prior Lead': prior_lead,
            'Posterior Lead': posterior_lead,
            'Prior Win Rate': prior_win_rate,
            'Posterior Win Rate': posterior_win_rate,
            'Drop': drop,
        },
        index=indices,
    )

    expected_p_win = trained_estimator.estimate(expected)
    actual_p_win = trained_estimator.estimate(actual)
    damage = expected_p_win - actual_p_win

    # The p(win) function that fuels the Damage function learned that playing bad moves when behind is likely to induce
    # a mistake and thus a comeback.  This results in generating negative Damage scores.  While this is unfortunately
    # true, this is not the sort of feedback a tool like this should provide.
    # A fix is to assume that the opponent will make the perfect response, calculate their p(win), and use 1 - that
    # value as the "actual" p(win) and to calculate the Damage.
    if damage < 0 < drop:
        projected = pd.Series(
            data={
                'Move': move + 1,
                'Prior Lead': -posterior_lead,
                'Posterior Lead': -posterior_lead,
                'Prior Win Rate': 1. - posterior_win_rate,
                'Posterior Win Rate': 1. - posterior_win_rate,
                'Drop': 0.,
            },
            index=indices,
        )
        actual_p_win = 1. - trained_estimator.estimate(projected)
        damage = expected_p_win - actual_p_win

    return 100. * damage, 100. * expected_p_win, 100. * actual_p_win