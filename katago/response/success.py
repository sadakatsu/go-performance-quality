from dataclasses import dataclass
from typing import List, Optional

from katago.response import RootInfo
from katago.response.moveinfo import MoveInfo
from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class SuccessResponse(SimpleJsonMixin):
    id: str
    is_during_search: bool
    move_infos: List[MoveInfo]
    root_info: RootInfo
    turn_number: int

    human_policy: Optional[List[float]] = None
    ownership: Optional[List[float]] = None
    ownership_stdev: Optional[float] = None
    policy: Optional[List[float]] = None
