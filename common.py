import re


def get_filename_core(analysis_filename: str):
    return re.match(r'^(?:[^\\/]*[\\/])*(.*)\.csv$', analysis_filename).group(1)