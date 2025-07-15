from dataclasses import dataclass, field
from typing import Union, Optional, List

from katago.shared import Coordinate, Pass
from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class MoveInfo(SimpleJsonMixin):
    edge_visits: int
    edge_weight: float
    lcb: float
    move: Union[Coordinate, Pass]
    order: int
    play_selection_value: float
    prior: float
    score_lead: float
    score_mean: float
    score_selfplay: float
    score_stdev: float
    utility: float
    utility_lcb: float
    visits: int
    weight: float
    winrate: float

    pv: List[Union[Coordinate, Pass]] = field(default_factory=list)

    human_prior: Optional[float] = None
    is_symmetry_of: Optional[Coordinate] = None
    ownership: Optional[List[float]] = None
    ownership_stdev: Optional[float] = None
    pv_edge_visits: Optional[int] = None
    pv_visits: Optional[int] = None
