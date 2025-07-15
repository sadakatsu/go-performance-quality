import numpy as np
import pandas as pd

from estimator.estimator import Estimator
from metrics import epsilon


class WeightedPDF:
    def __init__(self, X: pd.DataFrame, y: pd.Series, klass: int | float):
        """This requires that the features have already been extracted."""
        N = len(X)

        indices = y == klass
        subset = X[indices]
        self._proportion = len(subset) / N

        self._mu = subset.mean().to_numpy().reshape(-1, 1)

        # Pandas's covariance method has a fatal bug that somethimes generates impossible negative values for covariance
        # matrices.  Numpy handles this better, but requires two different approaches based upon the feature count.
        # :sigh:
        k = X.shape[1]
        if k == 1:
            self._sigma = np.array([np.var(subset, axis=0)])
        else:
            self._sigma = np.cov(subset.to_numpy().T)  # I don't @#$%ing get why they do it like this, but okay...

        # I am now paranoid.
        self._determinant = np.linalg.det(self._sigma)
        if self._determinant < epsilon:
            self._sigma = self._sigma + np.identity(k) * 1e-8
            self._determinant = np.linalg.det(self._sigma)
            if self._determinant < epsilon:
                raise ValueError(
                    f'Covariance matrix has an unusable determinant:\n{self._sigma},\n{self._determinant}'
                )

        self._inverse = np.linalg.inv(self._sigma)
        self._coefficient = 1. / (np.power(2 * np.pi, k / 2) * np.sqrt(self._determinant)) * self._proportion

        del subset
        del indices

    def estimate(self, row: pd.Series) -> float:
        """This requires that the features have already been extracted."""
        x = row.to_numpy().reshape(-1, 1)
        offset = x - self._mu
        return self._coefficient * np.exp(-0.5 * offset.T @ self._inverse @ offset)[0, 0]


class NormalDistributionEstimator(Estimator):
    def __init__(self, name: str, features: [str], X: pd.DataFrame, y: pd.Series):
        super().__init__(name, features)

        subset = X[features]
        self._win_pdf = WeightedPDF(subset, y, 1)
        self._loss_pdf = WeightedPDF(subset, y, 0)
        del subset

    def estimate(self, row: pd.Series) -> float:
        subset = self.extract_features(row)
        loss_term = self._loss_pdf.estimate(subset)
        loss_is_zero = loss_term < epsilon

        win_term = self._win_pdf.estimate(subset)
        win_is_zero = win_term < epsilon

        if loss_is_zero:
            if win_is_zero:
                result = 0.5
            else:
                result = 1.
        elif win_is_zero:
            result = 0.
        else:
            result = win_term / (win_term + loss_term)

        return result
