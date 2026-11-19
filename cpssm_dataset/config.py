"""Load the single YAML configuration used by every command."""

from copy import deepcopy
from pathlib import Path

import yaml


def load_configuration(path: Path, example: bool = False) -> dict:
    with path.open(encoding="utf-8") as stream:
        configuration = yaml.safe_load(stream)

    if not example:
        configuration["profile"] = "release"
        return configuration

    configuration = deepcopy(configuration)
    dataset = configuration["dataset"]
    profile = configuration["example"]
    dataset.update(
        output_directory=profile["output_directory"],
        duration_seconds=profile["duration_seconds"],
        u_values=profile["u_values"],
        seeds=profile["seeds"],
    )
    configuration["analysis"]["output_directory"] = configuration[
        "analysis"
    ]["example_output_directory"]
    configuration["profile"] = "example"
    return configuration


def configured_seeds(configuration: dict) -> list[int]:
    dataset = configuration["dataset"]
    if "seeds" in dataset:
        return [int(seed) for seed in dataset["seeds"]]
    first = int(dataset["seed_start"])
    return list(range(first, first + int(dataset["realization_count"])))

