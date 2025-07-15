from katago import HumanProfile


def simplify_human_profile(human_profile: HumanProfile) -> str:
    return 'pro' if human_profile.value.startswith('pro') else human_profile.value.split('_')[1]
