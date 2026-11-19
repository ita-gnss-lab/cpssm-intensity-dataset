"""Minimal example for inspecting the generated dataset."""

from cpssm_dataset import available_u_values, load_metadata, load_realization


directory = "data/example"
metadata = load_metadata(directory)
print(metadata)

u_value = float(available_u_values(directory)[0])
seed = int(metadata.loc[metadata["U"] == u_value, "seed"].iloc[0])
record = load_realization(directory, u_value, seed)
print(record.head())

