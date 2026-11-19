"""Fit SciPy's Rice distribution and compare it with measured intensities."""

from pathlib import Path
from time import perf_counter

from loguru import logger
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy import stats

from cpssm_dataset.io import iter_realizations, load_metadata


def _intensity_samples(
    directory: Path,
    u_value: float,
    column: str,
) -> np.ndarray:
    return np.concatenate(
        [
            frame[column].to_numpy(dtype=np.float64)
            for frame in iter_realizations(directory, u_value)
        ]
    )


def analyze_distributions(root: Path, configuration: dict) -> None:
    dataset = configuration["dataset"]
    settings = configuration["analysis"]
    data_directory = root / dataset["output_directory"]
    output_directory = root / settings["output_directory"]
    output_directory.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata(data_directory)
    selected = [
        value
        for value in settings["selected_u_values"]
        if np.any(np.isclose(metadata["U"], value))
    ]
    if not selected:
        raise ValueError("None of the selected U values is available.")

    lower, upper = settings["amplitude_range"]
    edges = np.linspace(lower, upper, settings["histogram_bin_count"] + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    colors = plt.colormaps["viridis"](np.linspace(0.1, 0.9, len(selected)))
    figure, axes = plt.subplots(
        1,
        3,
        figsize=(12.5, 3.6),
        sharex=True,
        sharey=True,
        layout="constrained",
    )
    results: list[dict] = []
    start = perf_counter()

    for band_index, (axis, band) in enumerate(zip(axes, dataset["bands"], strict=True)):
        for u_index, (u_value, color) in enumerate(zip(selected, colors, strict=True)):
            logger.info("Fitting {} at U={:g}", band, u_value)
            intensity = _intensity_samples(
                data_directory,
                u_value,
                f"{band}_intensity",
            )
            amplitude = np.sqrt(intensity)
            shape, _, scale = stats.rice.fit(amplitude, floc=0.0)
            empirical, _ = np.histogram(amplitude, bins=edges, density=True)
            fitted = stats.rice.pdf(
                centers,
                shape,
                loc=0.0,
                scale=scale,
            )
            axis.plot(
                centers,
                np.where(empirical > 0.0, empirical, np.nan),
                color=color,
                linewidth=1.5,
            )
            axis.plot(centers, fitted, color=color, linestyle="--", linewidth=1.3)

            results.append(
                {
                    "band": band,
                    "U": u_value,
                    "rice_shape": shape,
                    "rice_scale": scale,
                }
            )
            completed = band_index * len(selected) + u_index + 1
            total = len(dataset["bands"]) * len(selected)
            elapsed = perf_counter() - start
            logger.info(
                "Completed {}/{} fits; elapsed {:.1f} s, ETA {:.1f} s",
                completed,
                total,
                elapsed,
                elapsed * (total - completed) / completed,
            )
        axis.set_title(band)
        axis.set_xlabel(r"Amplitude $R=\sqrt{I}$")
        axis.set_ylim(settings["probability_density_range"])
        axis.grid(alpha=0.25)

    axes[0].set_ylabel("Probability density")
    axes[0].set_yscale("log")
    axes[0].legend(
        handles=[
            Line2D([], [], color="black", label="Measured"),
            Line2D([], [], color="black", linestyle="--", label="Fitted Rice"),
        ],
        loc="best",
    )
    color_map = plt.cm.ScalarMappable(
        norm=BoundaryNorm(np.arange(len(selected) + 1) - 0.5, len(selected)),
        cmap=ListedColormap(colors),
    )
    colorbar = figure.colorbar(color_map, ax=axes, pad=0.02)
    colorbar.set_ticks(range(len(selected)))
    colorbar.set_ticklabels(
        [
            f"U={value:g}; L1 S4={metadata.loc[np.isclose(metadata['U'], value), 'L1_S4'].mean():.2f}"
            for value in selected
        ]
    )
    figure.savefig(output_directory / "rice_amplitude_comparison.pdf")
    figure.savefig(output_directory / "rice_amplitude_comparison.png", dpi=200)
    plt.close(figure)
    pd.DataFrame(results).to_csv(output_directory / "rice_fit_parameters.csv", index=False)
    logger.info("Distribution comparison saved in {}", output_directory)

