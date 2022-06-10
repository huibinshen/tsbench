from tkinter.messagebox import NO
from typing import Iterator, Optional

import json
from pathlib import Path

from gluonts.dataset.common import Dataset
from gluonts.model.predictor import Predictor
from gluonts.model.forecast import QuantileForecast

try:
    from autogluon.timeseries import TimeSeriesPredictor, TimeSeriesDataFrame
except ImportError:
    TimeSeriesPredictor = None

AUTOGLUON_IS_INSTALLED = TimeSeriesPredictor is not None

USAGE_MESSAGE = """
Cannot import `autogluon`.

The `ProphetPredictor` is a thin wrapper for calling the `fbprophet` package.
In order to use it you need to install it using one of the following two
methods:

    # 1) install fbprophet directly
    pip install fbprophet

    # 2) install gluonts with the Prophet extras
    pip install gluonts[Prophet]
"""

class AutoGluonPredictor(Predictor):

    def __init__(self, model: TimeSeriesPredictor, prediction_length: int, freq: str, lead_time: int = 0) -> None:
        super().__init__(prediction_length, freq, lead_time)
        self.prediction_length = prediction_length
        self.freq = freq
        self.predictor = model
    
    # def predict(self, dataset: Dataset, **kwargs) -> Iterator[Forecast]:
    def predict(
        self,
        dataset: Dataset,
        num_samples: Optional[int] = None,
        num_workers: Optional[int] = None,
        num_prefetch: Optional[int] = None,
        **kwargs,
    ) -> Iterator[QuantileForecast]:
        data_frame = TimeSeriesDataFrame(dataset)
        outputs = self.predictor.predict(data_frame)
        metas = outputs.index.values
        cancat_len = outputs.shape[0]
        assert cancat_len % self.prediction_length == 0
        ts_num = cancat_len // self.prediction_length

        # TODO resault wraper
        colums = outputs.columns[1:]
        for i in range(ts_num):
            cur_val = outputs.values[i * self.prediction_length : (i + 1) * self.prediction_length, 1:]
            meta = metas[i * self.prediction_length : (i + 1) * self.prediction_length]
            yield QuantileForecast(
                forecast_arrays=cur_val.T,
                start_date=meta[0][1],
                freq=self.freq,
                forecast_keys=colums,
                item_id=meta[0][0])

    def deserialize(cls, path: Path, **kwargs) -> "Predictor":
        predictor = TimeSeriesPredictor.load(cls, path)  # type: ignore
        file = path / "metadata.pickle"
        with file.open("r") as f:
            meta = json.load(f)
        return AutoGluonPredictor(model=predictor,
            freq=meta["freq"], prediction_length=meta["prediction_length"]
        )

    def serialize(self, path: Path) -> None:
        self.predictor.save()
        file = path / "metadata.pickle"
        with file.open("w") as f:
            json.dump(
                {
                    "freq": self.freq,
                    "prediction_length": self.prediction_length,
                },
                f,
            )