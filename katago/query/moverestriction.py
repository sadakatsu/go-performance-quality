from dataclasses import dataclass, field
from typing import List, Union

from katago.shared import Coordinate, Pass, Player
from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class MoveRestriction(SimpleJsonMixin):
    player: Player
    until_depth: int

    moves: List[Union[Coordinate, Pass]] = field(default_factory=list)
