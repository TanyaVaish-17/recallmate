"""Filesystem locations used by the ML package."""
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
RAW_DIR = ML_DIR / "data" / "raw"            # git-ignored: downloaded / generated CSVs
PROCESSED_DIR = ML_DIR / "data" / "processed"  # git-ignored: train/val/test .npz files
ARTIFACTS_DIR = ML_DIR / "artifacts"          # preprocess_meta.json is committed; *.pt is ignored