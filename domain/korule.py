from enum import Enum


class KoRule(str, Enum):
    SIMPLE = 'SIMPLE'
    POSITIONAL = 'POSITIONAL'
    SITUATIONAL = 'SITUATIONAL'
