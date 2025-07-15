import time
from typing import List

from katago import Engine
from katago.response import SuccessResponse


def get_search_responses(
    engine: Engine,
    search_id: str,
    position_count: int,
    start: float
) -> List[SuccessResponse]:
    responses: List[SuccessResponse] = []
    done = 0
    while done < position_count:
        result: SuccessResponse = engine.next_response(search_id)
        if not result:
            time.sleep(1)
            continue
        responses.append(result)
        done += 1

        elapsed = time.time() - start
        print(
            f'{done} positions analyzed.  Position #{result.turn_number} completed; {elapsed:0.3f} seconds elapsed; '
            f'{elapsed / done:0.3f} SPP.'
        )
    responses.sort(key=lambda r: r.turn_number)
    return responses
