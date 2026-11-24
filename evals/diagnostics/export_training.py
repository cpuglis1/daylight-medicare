"""Build a training-only package for a judge tuner in an independently fenced workspace.

Writes only case files using the training partition. Launch the tuning role with
the exported folder as its sole corpus grant. The operator retains the complete
repository and runs validation outside the tuner. Exporting alone does not fence
a process that already has access to this repository.
"""

import argparse
import json
import os
from pathlib import Path
import tempfile

from validate_cases import CASE_DIR, JUDGES, validate_corpus


def export_training(destination):
    """Publish a new private directory of training fixtures, or fail before publication."""
    validate_corpus()
    if destination.exists():
        raise FileExistsError("Choose a new destination for the training package")
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        package = Path(temporary) / "training"
        package.mkdir(mode=0o700)
        for suite in sorted(JUDGES):
            lines = (CASE_DIR / (suite + ".jsonl")).read_text().splitlines()
            selected = [line for line in lines if json.loads(line)["split"] == "training"]
            (package / (suite + ".jsonl")).write_text("\n".join(selected) + "\n")
        os.rename(package, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    export_training(parser.parse_args().destination)
