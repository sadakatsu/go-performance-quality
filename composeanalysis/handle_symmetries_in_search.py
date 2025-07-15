from typing import List, Tuple, Dict, Union, Set

from katago import Coordinate, Pass
from katago.response import MoveInfo


def handle_symmetries_in_search(
    move_infos: List[MoveInfo]
) -> Tuple[
    List[MoveInfo],
    Dict[Union[Coordinate, Pass], MoveInfo],
    Dict[Union[Coordinate, Pass], Set[Union[Coordinate, Pass]]],
]:
    kept_infos: List[MoveInfo] = []
    move_to_info: Dict[Union[Coordinate, Pass], MoveInfo] = {}
    symmetries: Dict[Union[Coordinate, Pass], Set[Union[Coordinate, Pass]]] = {}
    for mi in move_infos:
        move = mi.move
        if mi.is_symmetry_of:
            entry = symmetries[mi.is_symmetry_of]
            entry.add(move)
            symmetries[move] = entry

            move_to_info[move] = move_to_info[mi.is_symmetry_of]
        else:
            symmetries[move] = {move}
            move_to_info[move] = mi
            kept_infos.append(mi)

    return kept_infos, move_to_info, symmetries
