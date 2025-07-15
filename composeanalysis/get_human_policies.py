import time
from typing import Dict, Optional, List

from composeanalysis.convert_to_policy_map import convert_to_policy_map
from katago import Engine, HumanProfile
from katago.response import SuccessResponse


def get_human_policies(
    engine: Engine,
    query_ids: Dict[Optional[HumanProfile], str],
    position_count: int,
    size: int,
) -> Dict[int, Dict[HumanProfile, Dict[str, float]]]:
    result: Dict[int, Dict[HumanProfile, Dict[str, float]]] = {}
    profiles_complete = 0
    total_profiles = (len(query_ids) - 1) * (position_count - 1)
    while profiles_complete < total_profiles:
        found = False
        for human_profile, query_id in query_ids.items():
            response: SuccessResponse = engine.next_response(query_id)
            if response is None:
                continue

            profiles_complete += 1
            found = True

            if response.turn_number not in result:
                turn_profiles: Dict[HumanProfile, Dict[str, float]] = {}
                result[response.turn_number] = turn_profiles
            else:
                turn_profiles = result[response.turn_number]

            turn_profiles[human_profile] = convert_to_policy_map(size, response.human_policy)

        if found:
            print(f'{profiles_complete} / {total_profiles} profiles complete...')

        if profiles_complete < total_profiles and not found:
            time.sleep(1)
    return result