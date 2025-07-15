from dataclasses import dataclass
from typing import Union

from katago.shared.coordinate import Coordinate
from katago.shared.passenum import Pass
from katago.shared.player import Player
from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class Placement(SimpleJsonMixin):
    player: Player
    location: Union[Coordinate, Pass]

    def __str__(self):
        return f'["{self.player.value}","{self.location.value}"]'
