import pandas as pd


class Estimator:
    def __init__(self, name: str, features: [str]):
        self._features = features
        self._name = name

    @property
    def features(self) -> [str]:
        return self._features[:]

    @property
    def name(self) -> str:
        return self._name

    def extract_features(self, row: pd.Series) -> pd.Series:
        return row[self._features]

    def estimate(self, row: pd.Series) -> float:
        raise NotImplementedError('Each Estimator subclass needs to define this.')
