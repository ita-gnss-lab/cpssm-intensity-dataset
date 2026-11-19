"""Small, memory-conscious readers for the published Parquet files."""

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


INTENSITY_COLUMNS = ["L1_intensity", "L2_intensity", "L5_intensity"]


def u_label(value: float) -> str:
    return f"{value:.12g}".replace("-", "m").replace(".", "p")


def data_file(directory: Path, u_value: float) -> Path:
    return directory / f"intensity_U_{u_label(u_value)}.parquet"


def load_metadata(directory: str | Path) -> pd.DataFrame:
    """Read the one-row-per-realization metadata table."""
    return pd.read_parquet(Path(directory) / "realizations.parquet")


def available_u_values(directory: str | Path) -> np.ndarray:
    """Return the sorted propagation strengths present in the dataset."""
    return np.sort(load_metadata(directory)["U"].unique())


def iter_realizations(
    directory: str | Path,
    u_value: float,
) -> Iterator[pd.DataFrame]:
    """Yield one realization at a time without loading an entire U file."""
    parquet = pq.ParquetFile(data_file(Path(directory), u_value))
    for row_group in range(parquet.num_row_groups):
        yield parquet.read_row_group(row_group).to_pandas()


def load_realization(
    directory: str | Path,
    u_value: float,
    seed: int,
    *,
    sampling_period_seconds: float = 0.01,
) -> pd.DataFrame:
    """Read one physical-intensity realization and add its time coordinate."""
    table = pq.read_table(
        data_file(Path(directory), u_value),
        filters=[("seed", "=", int(seed))],
    ).to_pandas()
    if table.empty:
        raise KeyError(f"No realization for U={u_value:g}, seed={seed}.")
    table["time_seconds"] = table["sample"] * sampling_period_seconds
    return table

