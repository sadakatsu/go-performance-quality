from typing import Union

from katago.shared import Coordinate, Pass


def str_to_enum(name: str) -> Union[Coordinate, Pass]:
    result: Union[Coordinate, Pass]

    if name.lower() == 'pass':
        result = Pass.PASS
    else:
        standard = name.upper()
        if standard in Coordinate:
            result = Coordinate(name)
        else:
            raise Exception('unknown move name')

    return result