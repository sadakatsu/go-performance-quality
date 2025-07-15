from typing import Union, NamedTuple

from katago.shared import Coordinate, Pass, Player


class MoveDTO(NamedTuple):
    player: Player
    move: Union[Coordinate, Pass]
