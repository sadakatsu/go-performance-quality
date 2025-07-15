import pandas as pd
import sklearn

from estimator.estimator import Estimator


class LogisticRegressionEstimator(Estimator):
    def __init__(self, name: str, features: [str], dof: int, X: pd.DataFrame, y: pd.Series):
        super().__init__(name, features)

        X = X[features].to_numpy()
        y = y.to_numpy()

        configuration = [('normalize', sklearn.preprocessing.StandardScaler())]
        if dof > 1:
            configuration.append(
                ('polynomial', sklearn.preprocessing.PolynomialFeatures(degree=dof, include_bias=False))
            )
        configuration.append(
            ('logistic-regression', sklearn.linear_model.LogisticRegression(solver='newton-cholesky', max_iter=1000))
        )

        self._pipe = sklearn.pipeline.Pipeline(configuration)
        self._pipe.fit(X, y)

    def estimate(self, row: pd.Series) -> float:
        x = self.extract_features(row).to_numpy().reshape(1, -1)
        return self._pipe.predict_proba(x)[0, 1]
