from typing import List, Dict

from composeanalysis.index_to_coordinate_label import index_to_coordinate_label


def convert_to_policy_map(size: int, raw_policy: List[float]) -> Dict[str, float]:
    policy: Dict[str, float] = {}
    for i, value in enumerate(raw_policy):
        if value < -0.5:
            continue
        label = index_to_coordinate_label(i, size)
        policy[label] = value
    return policy
