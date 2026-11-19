"""Generate CPSSM intensity records and package them as Parquet."""

from pathlib import Path
import shutil
import subprocess
from time import perf_counter

from loguru import logger
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from cpssm_dataset.config import configured_seeds
from cpssm_dataset.io import INTENSITY_COLUMNS, data_file, u_label


def _matlab_text(value: Path | str) -> str:
    return str(value).replace("'", "''")


def _generate_csv(
    root: Path,
    configuration: dict,
    u_value: float,
    seeds: list[int],
    directory: Path,
) -> None:
    matlab = shutil.which("matlab")
    if matlab is None:
        raise RuntimeError("MATLAB is required for CPSSM generation.")

    dataset = configuration["dataset"]
    spectrum = dataset["spectral_parameters"]
    bands = ",".join(dataset["bands"])
    frequencies = " ".join(str(value) for value in dataset["frequencies_hz"])
    seed_values = " ".join(str(seed) for seed in seeds)
    command = (
        f"addpath('{_matlab_text(root / 'matlab')}');"
        "generate_intensity_dataset("
        f"'{_matlab_text(directory)}',"
        f"'{_matlab_text(root / dataset['simulator_directory'])}',"
        f"{dataset['duration_seconds']:.17g},"
        f"{dataset['sampling_period_seconds']:.17g},"
        f"[{seed_values}],"
        f"[{u_value:.17g} {spectrum['mu0']:.17g} "
        f"{spectrum['p1']:.17g} {spectrum['p2']:.17g}],"
        f"{dataset['rhof_veff_ratio_seconds']:.17g},"
        f"'{bands}',[{frequencies}]);"
    )
    subprocess.run([matlab, "-batch", command], cwd=root, check=True)


def _missing_csv_seeds(
    directory: Path,
    seeds: list[int],
    expected_sample_count: int,
) -> list[int]:
    """Return seeds without a complete intermediate record."""
    missing = []
    for seed in seeds:
        path = directory / f"seed_{seed}.csv"
        try:
            values = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
            valid = (
                values.shape == (expected_sample_count, 4)
                and np.array_equal(values[:, 0], np.arange(expected_sample_count))
                and np.all(np.isfinite(values[:, 1:]))
                and np.all(values[:, 1:] >= 0.0)
            )
        except (OSError, ValueError):
            valid = False
        if not valid:
            missing.append(seed)
    return missing


def _convert_to_parquet(
    csv_directory: Path,
    output_file: Path,
    u_value: float,
    seeds: list[int],
    compression: str,
) -> None:
    schema = pa.schema(
        [
            ("U", pa.float32()),
            ("seed", pa.int32()),
            ("sample", pa.int32()),
            *((name, pa.float32()) for name in INTENSITY_COLUMNS),
        ]
    )
    temporary = output_file.with_suffix(".temporary.parquet")
    start = perf_counter()
    with pq.ParquetWriter(temporary, schema, compression=compression) as writer:
        for index, seed in enumerate(seeds, start=1):
            values = np.loadtxt(
                csv_directory / f"seed_{seed}.csv",
                delimiter=",",
                skiprows=1,
                ndmin=2,
            )
            if values.shape[1] != 4 or np.any(values[:, 1:] < 0):
                raise ValueError(f"Invalid intensity data for seed {seed}.")
            sample = values[:, 0].astype(np.int32)
            if not np.array_equal(sample, np.arange(len(sample))):
                raise ValueError(f"Nonconsecutive samples for seed {seed}.")
            table = pa.table(
                {
                    "U": np.full(len(values), u_value, dtype=np.float32),
                    "seed": np.full(len(values), seed, dtype=np.int32),
                    "sample": sample,
                    **{
                        name: values[:, column].astype(np.float32)
                        for column, name in enumerate(INTENSITY_COLUMNS, start=1)
                    },
                },
                schema=schema,
            )
            writer.write_table(table)
            if index == len(seeds) or index % max(1, len(seeds) // 10) == 0:
                elapsed = perf_counter() - start
                eta = elapsed * (len(seeds) - index) / index
                logger.info(
                    "U={:g}: converted {}/{} realizations; elapsed {:.1f} s, ETA {:.1f} s",
                    u_value,
                    index,
                    len(seeds),
                    elapsed,
                    eta,
                )
    temporary.replace(output_file)


def _s4(intensity: np.ndarray) -> float:
    values = np.asarray(intensity, dtype=np.float64)
    mean = np.mean(values)
    return float(np.sqrt(max(np.mean(values**2) / mean**2 - 1.0, 0.0)))


def _write_metadata(configuration: dict, output_directory: Path) -> None:
    rows: list[dict] = []
    u_values = configuration["dataset"]["u_values"]
    start = perf_counter()
    for index, u_value in enumerate(u_values, start=1):
        logger.info("Summarizing realized S4 for U={:g}", u_value)
        parquet = pq.ParquetFile(data_file(output_directory, u_value))
        for row_group in range(parquet.num_row_groups):
            frame = parquet.read_row_group(row_group).to_pandas()
            row = {
                "U": float(u_value),
                "seed": int(frame["seed"].iat[0]),
                "sample_count": len(frame),
            }
            for band in configuration["dataset"]["bands"]:
                intensity = frame[f"{band}_intensity"].to_numpy()
                row[f"{band}_mean_intensity"] = float(np.mean(intensity))
                row[f"{band}_S4"] = _s4(intensity)
            rows.append(row)
        elapsed = perf_counter() - start
        logger.info(
            "Summarized {}/{} U values; elapsed {:.1f} s, ETA {:.1f} s",
            index,
            len(u_values),
            elapsed,
            elapsed * (len(u_values) - index) / index,
        )

    metadata = pd.DataFrame(rows).sort_values(["U", "seed"])
    metadata.to_parquet(output_directory / "realizations.parquet", index=False)
    mapping = metadata.groupby("U", as_index=False)["L1_S4"].agg(
        L1_S4_mean="mean",
        L1_S4_std="std",
        L1_S4_min="min",
        L1_S4_max="max",
    )
    mapping.to_csv(output_directory / "u_s4_mapping.csv", index=False)


def generate_dataset(
    root: Path,
    configuration: dict,
    *,
    regenerate: bool = False,
) -> None:
    dataset = configuration["dataset"]
    seeds = configured_seeds(configuration)
    output_directory = root / dataset["output_directory"]
    output_directory.mkdir(parents=True, exist_ok=True)
    start = perf_counter()

    for index, u_value in enumerate(dataset["u_values"], start=1):
        output_file = data_file(output_directory, u_value)
        if output_file.exists() and not regenerate:
            logger.info("U={:g}: using existing {}", u_value, output_file)
            continue
        intermediate = root / "data" / "intermediate" / f"U_{u_label(u_value)}"
        intermediate.mkdir(parents=True, exist_ok=True)
        expected_count = round(
            dataset["duration_seconds"] / dataset["sampling_period_seconds"]
        )
        missing_seeds = _missing_csv_seeds(intermediate, seeds, expected_count)
        logger.info(
            "Generating U={:g} ({}/{}): {} of {} realizations are missing",
            u_value,
            index,
            len(dataset["u_values"]),
            len(missing_seeds),
            len(seeds),
        )
        if missing_seeds:
            _generate_csv(root, configuration, u_value, missing_seeds, intermediate)
        _convert_to_parquet(
            intermediate,
            output_file,
            u_value,
            seeds,
            dataset["parquet_compression"],
        )
        if not dataset["keep_intermediate_csv"]:
            shutil.rmtree(intermediate)
        elapsed = perf_counter() - start
        eta = elapsed * (len(dataset["u_values"]) - index) / index
        logger.info(
            "Completed U={:g}; total elapsed {:.1f} s, sweep ETA {:.1f} s",
            u_value,
            elapsed,
            eta,
        )

    _write_metadata(configuration, output_directory)
    logger.info("Dataset and U/S4 mapping saved in {}", output_directory)

