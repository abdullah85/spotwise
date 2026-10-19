"""Tests run on SYNTHETIC data in a temp dir, never on real data or a database."""

import importlib.util
import json
import os
import tempfile
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
_tmp = Path(tempfile.mkdtemp(prefix="spotwise-test-"))
os.environ["SPOTWISE_DATA_DIR"] = str(_tmp)

_spec = importlib.util.spec_from_file_location(
    "make_sample", Path(__file__).resolve().parents[1] / "scripts" / "make_sample.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
(_tmp / "sample_prices.json").write_text(json.dumps(_mod.build()))
