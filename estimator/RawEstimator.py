import pandas as pd

from estimator.estimator import Estimator


class RawEstimator(Estimator):
    def __init__(self, name: str, features: [str], threshold: float):
        super().__init__(name, features)
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    def estimate(self, row: pd.Series) -> float:
        return 1. if self.extract_features(row).to_numpy()[0] >= self.threshold else 0.
