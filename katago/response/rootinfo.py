from dataclasses import dataclass
from typing import Optional

from katago.shared import Player
from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class RootInfo(SimpleJsonMixin):
    current_player: Player
    raw_lead: float
    raw_no_result_prob: float
    raw_score_selfplay: float
    raw_score_selfplay_stdev: float
    raw_st_score_error: float
    raw_st_wr_error: float
    raw_var_time_left: float
    raw_winrate: float
    score_selfplay: float
    score_lead: float
    score_stdev: float
    sym_hash: str
    this_hash: str
    utility: float
    visits: int
    weight: float
    winrate: float

    human_score_mean: Optional[float] = None
    human_score_stdev: Optional[float] = None
    human_st_score_error: Optional[float] = None
    human_st_wr_error: Optional[float] = None
    human_winrate: Optional[float] = None