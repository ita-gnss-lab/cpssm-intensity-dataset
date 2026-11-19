# CPSSM triple-frequency intensity dataset

This repository generates and analyzes jointly simulated GPS L1, L2, and L5
ionospheric-scintillation intensities. It varies the CPSSM propagation strength
`U`, records the realized L1/L2/L5 `S4`, and compares measured intensity
densities with Rice distributions fitted by SciPy.

The final configuration contains 12 values of `U`, 100 realizations per value,
300 s per realization, and a 10 ms sampling period. Every parameter is in
[`params.yaml`](params.yaml).

## Setup

Requirements:

- Python 3.11 or newer;
- MATLAB;
- Git and Git submodules;
- `uv` for the commands below.

```bash
git submodule update --init
uv sync
```

The simulator is pinned to commit
`175b2ec9e30b802f5ac0ed1d158cd673ae14092b`.

## Check the complete pipeline quickly

The example uses three `U` values, two seeds, and five seconds per record:

```bash
uv run python main.py all --example
uv run python examples/read_dataset.py
```

Progress messages report completed realizations, elapsed time, and ETA.

## Generate and analyze the final dataset

```bash
uv run python main.py generate
uv run python main.py analyze
```

Existing Parquet files are reused. Add `--regenerate` to the generation command
to replace them. The generated data are deliberately excluded from Git and are
managed by DVC:

```bash
uv run dvc repro
```

## Dataset schema

There is one Parquet file per `U`. Each realization is one Parquet row group,
so it can be read without loading the complete file.

| Column | Type | Meaning |
|---|---|---|
| `U` | float32 | CPSSM propagation-strength parameter |
| `seed` | int32 | simulator seed shown in the metadata |
| `sample` | int32 | zero-based sample index |
| `L1_intensity` | float32 | physical L1 intensity |
| `L2_intensity` | float32 | physical L2 intensity |
| `L5_intensity` | float32 | physical L5 intensity |

`realizations.parquet` contains one row per realization with the mean intensity
and realized `S4` of each frequency. `u_s4_mapping.csv` is the requested mapping
between `U` and the realized L1 `S4` ensemble.

```python
from cpssm_dataset import load_realization

record = load_realization(
    "data/release",
    u_value=1.0,
    seed=2000,
)
print(record)
```

Use `iter_realizations()` when processing the full dataset with limited memory.

## Distribution comparison

For each selected `U` and frequency, SciPy fits its Rice amplitude distribution
to the physical CPSSM amplitude `sqrt(I)` with
`scipy.stats.rice.fit(..., floc=0)`. Both the measured histogram and fitted
curve show physical amplitude; the fitted curve is evaluated directly with
`scipy.stats.rice.pdf`. No custom distribution fitter is implemented here.

### Rice-fit parameters

`rice_fit_parameters.csv` contains one row for every analyzed frequency and
`U`. The Rice model is fitted to the physical amplitude `R = sqrt(I)` using
[`scipy.stats.rice.fit`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rice.html)
with `floc=0`. SciPy's generic
[`fit`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rv_continuous.fit.html)
uses maximum-likelihood estimation by default.

| Column | Definition | Interpretation |
|---|---|---|
| `rice_shape` | SciPy's dimensionless Rice shape `b = nu / sigma`, where `nu` is the coherent-field magnitude and `sigma` is the standard deviation of each Gaussian field component. | `b` near zero approaches Rayleigh fading; larger `b` indicates a stronger coherent component. It is not a goodness-of-fit score. |
| `rice_scale` | SciPy's fitted Rice `scale = sigma`, in amplitude units. | Controls the absolute random-amplitude scale. It is not an intensity parameter or a goodness-of-fit score. |

The fitted amplitude density is evaluated directly with
[`scipy.stats.rice.pdf`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rice.html).
The dataset itself continues to store physical intensity, and the plotting
code obtains amplitude as `sqrt(I)`.

## Publish to Kaggle

Set `publication.kaggle_owner` in `params.yaml` and authenticate the official
Kaggle client. Keep `publication.public: false` for the first inspection.

```bash
uv run python main.py publish
```

Set `publication.mode` to `version` for later releases. The publisher prepares
a staging directory containing the Parquet files, metadata, fitted parameters,
and figures before calling the official Kaggle Python API. Credentials are
never read from or written to this repository.

## Provenance and licenses

The CPSSM and original GNSS Scintillation Simulator were developed by the
[CU SENSE Lab](https://github.com/cu-sense-lab/gnss-scintillation-simulator).
This dataset is generated with the pinned, refactored
[ITA GPS/GNSS Laboratory fork](https://github.com/ita-gnss-lab/gnss-scintillation-simulator).
The fork is implementation provenance; it is not presented as the origin of
the model. Repository code is MIT licensed. Generated data are released under
CC BY 4.0; see
[`DATA_LICENSE.md`](DATA_LICENSE.md).

