"""Command-line entry point for the complete dataset workflow."""

from argparse import ArgumentParser
from pathlib import Path
from time import perf_counter

from loguru import logger

from cpssm_dataset.analysis import analyze_distributions
from cpssm_dataset.config import load_configuration
from cpssm_dataset.generation import generate_dataset
from cpssm_dataset.publication import publish_dataset


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("generate", "analyze", "all", "publish"),
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Use the small example profile from params.yaml.",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Replace existing Parquet files during generation.",
    )
    arguments = parser.parse_args()

    root = Path(__file__).resolve().parent
    configuration = load_configuration(root / "params.yaml", arguments.example)
    start = perf_counter()

    if arguments.command in {"generate", "all"}:
        generate_dataset(root, configuration, regenerate=arguments.regenerate)
    if arguments.command in {"analyze", "all"}:
        analyze_distributions(root, configuration)
    if arguments.command == "publish":
        if arguments.example:
            parser.error("The example dataset cannot be published.")
        publish_dataset(root, configuration)

    logger.info("{} completed in {:.1f} s", arguments.command, perf_counter() - start)


if __name__ == "__main__":
    main()

