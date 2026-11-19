"""Prepare and publish the dataset with Kaggle's official Python API."""

import json
import os
from pathlib import Path
import shutil
from time import perf_counter

from kaggle.api.kaggle_api_extended import KaggleApi
from loguru import logger


def _link_files(source: Path, destination: Path) -> None:
    for file in source.iterdir():
        if not file.is_file():
            continue
        target = destination / file.name
        try:
            os.link(file, target)
        except OSError:
            shutil.copy2(file, target)


def publish_dataset(root: Path, configuration: dict) -> None:
    settings = configuration["publication"]
    owner = settings["kaggle_owner"].strip()
    if not owner:
        raise ValueError("Set publication.kaggle_owner in params.yaml first.")

    staging = root / settings["upload_directory"]
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    _link_files(root / configuration["dataset"]["output_directory"], staging)
    _link_files(root / configuration["analysis"]["output_directory"], staging)
    for name in ("README.md", "params.yaml", "DATA_LICENSE.md", "CITATION.cff"):
        shutil.copy2(root / name, staging / name)

    metadata = {
        "title": configuration["dataset"]["title"],
        "id": f"{owner}/{settings['dataset_slug']}",
        "licenses": [{"name": "CC-BY-4.0"}],
        "description": configuration["dataset"]["description"],
    }
    with (staging / "dataset-metadata.json").open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2)

    logger.info("Uploading {} to Kaggle", metadata["id"])
    start = perf_counter()
    api = KaggleApi()
    api.authenticate()
    if settings["mode"] == "create":
        response = api.dataset_create_new(
            str(staging),
            public=settings["public"],
            convert_to_csv=False,
        )
    elif settings["mode"] == "version":
        response = api.dataset_create_version(
            str(staging),
            settings["version_message"],
            convert_to_csv=False,
        )
    else:
        raise ValueError("publication.mode must be 'create' or 'version'.")
    logger.info("Kaggle upload completed in {:.1f} s", perf_counter() - start)
    logger.info("Kaggle response: {}", response)

