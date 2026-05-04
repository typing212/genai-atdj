#!/usr/bin/env python3
"""
librosa_extract.py

Extract librosa audio features for all MP3s in a flat folder:

    sample/style/
      AlbumName__song1.mp3
      AlbumName__song2.mp3

Output CSV columns:
    album, filename, <librosa-only features>

Features: mfcc (1-13), delta_mfcc, chroma, spectral_contrast,
      spectral_bandwidth, rms, onset_strength, tempogram summary,
      harmonic/percussive energy ratios.

Usage:
    python librosa_extract.py \\
        --input-root sample/milonga \\
        --output-csv librosa_milonga.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import librosa


N_MFCC = 13


# Helpers

def stats_1d(x: Any, prefix: str) -> Dict[str, float]:
    x = np.asarray(x).flatten()
    return {
        f"{prefix}_mean": float(np.mean(x)),
        f"{prefix}_std": float(np.std(x)),
    }


def stats_2d_by_row(x: Any, prefix: str) -> Dict[str, float]:
    x = np.asarray(x)
    out: Dict[str, float] = {}
    for i in range(x.shape[0]):
        out[f"{prefix}_{i + 1}_mean"] = float(np.mean(x[i]))
        out[f"{prefix}_{i + 1}_std"] = float(np.std(x[i]))
    return out


def split_album_and_filename(file_name: str) -> Tuple[str, str]:
    """
    Expect filenames like:  AlbumName__Original Song Name.mp3
    Split only on the first '__' so the original filename can still contain '__'.
    """
    if "__" in file_name:
        album, original_name = file_name.split("__", 1)
        return album, original_name
    return "", file_name


# Feature extraction

def extract_audio_features(mp3_path: Path) -> Dict[str, Any]:
    y, sr = librosa.load(str(mp3_path), sr=None, mono=True)

    album, original_filename = split_album_and_filename(mp3_path.name)

    features: Dict[str, Any] = {
        "album": album,
        "filename": original_filename,
    }

    # MFCC (13 coefficients × mean/std)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    features.update(stats_2d_by_row(mfcc, "mfcc"))

    # Delta MFCC
    features.update(stats_2d_by_row(librosa.feature.delta(mfcc), "delta_mfcc"))

    # Chroma
    features.update(stats_2d_by_row(librosa.feature.chroma_stft(y=y, sr=sr), "chroma"))

    # Spectral contrast
    features.update(stats_2d_by_row(librosa.feature.spectral_contrast(y=y, sr=sr), "spectral_contrast"))

    # Spectral bandwidth
    features.update(stats_1d(librosa.feature.spectral_bandwidth(y=y, sr=sr), "spectral_bandwidth"))

    # RMS energy
    features.update(stats_1d(librosa.feature.rms(y=y), "rms"))

    # Onset strength
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    features.update(stats_1d(onset_env, "onset_strength"))

    # Tempogram summary
    tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
    features["tempogram_global_mean"] = float(np.mean(tempogram))
    features["tempogram_global_std"] = float(np.std(tempogram))
    features["tempogram_max_bin_strength"] = float(np.max(np.mean(tempogram, axis=1)))

    # Harmonic / percussive separation
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    harmonic_energy = float(np.sum(y_harmonic ** 2))
    percussive_energy = float(np.sum(y_percussive ** 2))
    total_energy = harmonic_energy + percussive_energy

    features["harmonic_energy"] = harmonic_energy
    features["percussive_energy"] = percussive_energy
    features["harmonic_to_percussive_ratio"] = (
        harmonic_energy / percussive_energy if percussive_energy > 0 else np.nan
    )
    features["harmonic_energy_ratio"] = (
        harmonic_energy / total_energy if total_energy > 0 else np.nan
    )
    features["percussive_energy_ratio"] = (
        percussive_energy / total_energy if total_energy > 0 else np.nan
    )

    return features


# File discovery

def find_mp3_files(input_root: Path) -> List[Path]:
    return sorted(p for p in input_root.glob("*.mp3") if p.is_file())


# Main

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract librosa features from a flat folder of MP3s."
    )
    parser.add_argument("--input-root", required=True,
                        help="Flat folder of MP3s, e.g. sample/milonga")
    parser.add_argument("--output-csv", default="librosa_features.csv",
                        help="Output CSV path (default: librosa_features.csv)")
    parser.add_argument("--max-files", type=int, default=None,
                        help="Cap the number of files processed (useful for testing)")
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output_csv = Path(args.output_csv)

    if not input_root.is_dir():
        raise NotADirectoryError(f"Input root not found or not a directory: {input_root}")

    mp3_files = find_mp3_files(input_root)
    if not mp3_files:
        raise FileNotFoundError(f"No .mp3 files found under: {input_root}")
    if args.max_files:
        mp3_files = mp3_files[:args.max_files]

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    total = len(mp3_files)

    print(f"Processing {total} MP3 files from: {input_root}")

    for i, mp3_path in enumerate(mp3_files, start=1):
        print(f"[{i}/{total}] {mp3_path.name}")
        try:
            rows.append(extract_audio_features(mp3_path))
        except Exception as e:
            album, original_filename = split_album_and_filename(mp3_path.name)
            print(f"  ERROR: {e}")
            errors.append({"album": album, "filename": original_filename, "error": str(e)})

    df = pd.DataFrame(rows)
    front_cols = ["album", "filename"]
    df = df[front_cols + [c for c in df.columns if c not in front_cols]]
    df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"\nSaved {len(rows)} rows → {output_csv}")

    if errors:
        error_path = output_csv.with_stem(output_csv.stem + "_errors")
        pd.DataFrame(errors).to_csv(error_path, index=False, encoding="utf-8")
        print(f"Saved {len(errors)} errors → {error_path}")


if __name__ == "__main__":
    main()
