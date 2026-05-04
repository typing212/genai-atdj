#!/usr/bin/env python3
"""
essentia_extract.py

Extract Essentia handcrafted descriptors + TF model predictions for all MP3s
in a flat folder:

    sample/style/
      AlbumName__song1.mp3
      AlbumName__song2.mp3

Output CSV columns:
    album, filename, <handcrafted features>, <model predictions>

Features: bpm, duration, key/scale/harmony, danceability, loudness, spectral
      descriptors, and all TF model predictions.

Usage:
    python essentia_extract.py \\
        --input-root  sample/milonga \\
        --output-csv  essentia_milonga.csv \\
        --models-dir  models/
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from essentia.standard import (
    MusicExtractor,
    MonoLoader,
    TensorflowPredict2D,
    TensorflowPredictEffnetDiscogs,
    TensorflowPredictMusiCNN,
)


# Helpers

def to_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def safe_pool_value(pool: Any, key: str, default: Any = None) -> Any:
    try:
        return pool[key]
    except Exception:
        return default


def sanitize_label(label: str) -> str:
    label = str(label).strip().lower()
    label = label.replace("&", "and")
    label = re.sub(r"[/\s\-]+", "_", label)
    label = re.sub(r"[^a-z0-9_]+", "", label)
    label = re.sub(r"_+", "_", label).strip("_")
    return label


def unique_preserve_order(items: List[Optional[str]]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item is None:
            continue
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_class_names_from_metadata(metadata_path: Path) -> List[str]:
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))

    candidates = [
        meta.get("classes"),
        meta.get("classes", {}).get("name") if isinstance(meta.get("classes"), dict) else None,
        meta.get("schema", {}).get("classes"),
        meta.get("model", {}).get("classes"),
        meta.get("classes_names"),
        meta.get("class_names"),
        meta.get("output_metadata", {}).get("classes"),
        meta.get("classes", {}).get("labels") if isinstance(meta.get("classes"), dict) else None,
    ]

    for c in candidates:
        if isinstance(c, list) and len(c) > 0:
            return [str(x) for x in c]

    found: List[str] = []

    def walk(obj: Any) -> None:
        nonlocal found
        if found:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).lower()
                if lk in {"classes", "class_names", "classes_names", "labels"} and isinstance(v, list):
                    found = [str(x) for x in v]
                    return
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(meta)
    return found


def aggregate_predictions(preds: Any) -> np.ndarray:
    arr = np.array(preds)
    arr = np.squeeze(arr)
    if arr.ndim == 1:
        return arr.astype(float)
    if arr.ndim == 2:
        return arr.mean(axis=0).astype(float)
    raise ValueError(f"Unexpected prediction shape: {arr.shape}")


def predictions_to_dict(preds: np.ndarray, labels: List[str], prefix: str) -> Dict[str, float]:
    if len(labels) != len(preds):
        raise ValueError(f"Label count {len(labels)} != prediction count {len(preds)}")
    return {f"{prefix}{sanitize_label(label)}": float(score) for label, score in zip(labels, preds)}


def pick_score_by_keyword(
    d: Dict[str, Any],
    prefix: str,
    positive_keywords: List[str],
    negative_keywords: List[str],
) -> Optional[float]:
    candidates = []
    for k, v in d.items():
        if not k.startswith(prefix):
            continue
        lk = k.lower()
        if any(pk in lk for pk in positive_keywords):
            if not any(nk in lk for nk in negative_keywords):
                candidates.append((k, v))

    if len(candidates) == 1:
        return float(candidates[0][1])

    for k, v in d.items():
        if not k.startswith(prefix):
            continue
        lk = k.lower()
        if any(lk.endswith(pk) for pk in positive_keywords):
            if not any(nk in lk for nk in negative_keywords):
                return float(v)

    return None


def split_album_and_filename(file_name: str) -> Tuple[str, str]:
    """
    Expect filenames like:  AlbumName__Original Song Name.mp3
    Split only on the first '__' so original filename can still contain '__'.
    """
    if "__" in file_name:
        album, original_name = file_name.split("__", 1)
        return album, original_name
    return "", file_name


# Handcrafted features (Essentia owns these)

def extract_handcrafted_features(audio_path: Path) -> Dict[str, Any]:
    extractor = MusicExtractor(
        lowlevelStats=["mean", "stdev"],
        rhythmStats=["mean", "stdev"],
        tonalStats=["mean", "stdev"],
    )
    pool, _ = extractor(str(audio_path))

    features: Dict[str, Any] = {
        # --- identity / timing ---
        "duration": to_float(safe_pool_value(pool, "metadata.audio_properties.length")),

        # --- rhythm (Essentia owns bpm) ---
        "bpm": to_float(safe_pool_value(pool, "rhythm.bpm")),
        "onset_rate": to_float(safe_pool_value(pool, "rhythm.onset_rate")),
        "danceability": to_float(safe_pool_value(pool, "rhythm.danceability")),

        # --- tonal ---
        "key": safe_pool_value(pool, "tonal.key_krumhansl.key"),
        "scale": safe_pool_value(pool, "tonal.key_krumhansl.scale"),
        "key_strength": to_float(safe_pool_value(pool, "tonal.key_krumhansl.strength")),
        "chords_changes_rate": to_float(safe_pool_value(pool, "tonal.chords_changes_rate")),
        "chords_number_rate": to_float(safe_pool_value(pool, "tonal.chords_number_rate")),
        "hpcp_entropy": to_float(safe_pool_value(pool, "tonal.hpcp_entropy.mean")),
        "tuning_frequency": to_float(safe_pool_value(pool, "tonal.tuning_frequency")),

        # --- low-level / dynamics ---
        "average_loudness": to_float(safe_pool_value(pool, "lowlevel.average_loudness")),
        "dynamic_complexity": to_float(safe_pool_value(pool, "lowlevel.dynamic_complexity")),
        "spectral_centroid_mean": to_float(safe_pool_value(pool, "lowlevel.spectral_centroid.mean")),
        "spectral_centroid_stdev": to_float(safe_pool_value(pool, "lowlevel.spectral_centroid.stdev")),
        "spectral_complexity_mean": to_float(safe_pool_value(pool, "lowlevel.spectral_complexity.mean")),
        "spectral_energy_mean": to_float(safe_pool_value(pool, "lowlevel.spectral_energy.mean")),
        "spectral_rolloff_mean": to_float(safe_pool_value(pool, "lowlevel.spectral_rolloff.mean")),
        "spectral_flux_mean": to_float(safe_pool_value(pool, "lowlevel.spectral_flux.mean")),
        "dissonance_mean": to_float(safe_pool_value(pool, "lowlevel.dissonance.mean")),
        "zerocrossingrate_mean": to_float(safe_pool_value(pool, "lowlevel.zerocrossingrate.mean")),
    }

    return features


# Model registry

MODEL_SPECS = {
    "is_danceable": {
        "embedder": "msd_musicnn",
        "classifier_pb": "danceability-msd-musicnn-1.pb",
        "classifier_meta": "danceability-msd-musicnn-1.json",
        "prefix": "is_danceable_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "voice_instrumental": {
        "embedder": "msd_musicnn",
        "classifier_pb": "voice_instrumental-msd-musicnn-1.pb",
        "classifier_meta": "voice_instrumental-msd-musicnn-1.json",
        "prefix": "voice_instrumental_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "voice_gender": {
        "embedder": "msd_musicnn",
        "classifier_pb": "gender-msd-musicnn-1.pb",
        "classifier_meta": "gender-msd-musicnn-1.json",
        "prefix": "voice_gender_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "mood_happy": {
        "embedder": "msd_musicnn",
        "classifier_pb": "mood_happy-msd-musicnn-1.pb",
        "classifier_meta": "mood_happy-msd-musicnn-1.json",
        "prefix": "mood_happy_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "mood_sad": {
        "embedder": "msd_musicnn",
        "classifier_pb": "mood_sad-msd-musicnn-1.pb",
        "classifier_meta": "mood_sad-msd-musicnn-1.json",
        "prefix": "mood_sad_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "mood_relaxed": {
        "embedder": "msd_musicnn",
        "classifier_pb": "mood_relaxed-msd-musicnn-1.pb",
        "classifier_meta": "mood_relaxed-msd-musicnn-1.json",
        "prefix": "mood_relaxed_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "mood_aggressive": {
        "embedder": "msd_musicnn",
        "classifier_pb": "mood_aggressive-msd-musicnn-1.pb",
        "classifier_meta": "mood_aggressive-msd-musicnn-1.json",
        "prefix": "mood_aggressive_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "mood_party": {
        "embedder": "msd_musicnn",
        "classifier_pb": "mood_party-msd-musicnn-1.pb",
        "classifier_meta": "mood_party-msd-musicnn-1.json",
        "prefix": "mood_party_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "mood_acoustic": {
        "embedder": "msd_musicnn",
        "classifier_pb": "mood_acoustic-msd-musicnn-1.pb",
        "classifier_meta": "mood_acoustic-msd-musicnn-1.json",
        "prefix": "mood_acoustic_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "mood_electronic": {
        "embedder": "msd_musicnn",
        "classifier_pb": "mood_electronic-msd-musicnn-1.pb",
        "classifier_meta": "mood_electronic-msd-musicnn-1.json",
        "prefix": "mood_electronic_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
    "moods_mirex": {
        "embedder": "msd_musicnn",
        "classifier_pb": "moods_mirex-msd-musicnn-1.pb",
        "classifier_meta": "moods_mirex-msd-musicnn-1.json",
        "prefix": "mirex_mood_",
        "classifier_input_candidates": [
            "serving_default_model_Placeholder",
            "model/Placeholder",
        ],
        "classifier_output_candidates": [
            "PartitionedCall",
            "PartitionedCall:0",
            "model/Softmax",
            "model/Sigmoid",
        ],
    },
    "mtg_jamendo_top50tags": {
        "embedder": "discogs_effnet",
        "classifier_pb": "mtg_jamendo_top50tags-discogs-effnet-1.pb",
        "classifier_meta": "mtg_jamendo_top50tags-discogs-effnet-1.json",
        "prefix": "jamendo_",
        "classifier_output_candidates": ["model/Sigmoid", "model/Softmax"],
    },
    "nsynth_instrument": {
        "embedder": "discogs_effnet",
        "classifier_pb": "nsynth_instrument-discogs-effnet-1.pb",
        "classifier_meta": "nsynth_instrument-discogs-effnet-1.json",
        "prefix": "nsynth_instrument_",
        "classifier_output_candidates": ["model/Softmax", "model/Sigmoid"],
    },
}

EMBEDDER_SPECS = {
    "msd_musicnn": {
        "loader_sr": 16000,
        "graph": "msd-musicnn-1.pb",
        "builder": lambda pb: TensorflowPredictMusiCNN(
            graphFilename=str(pb),
            output="model/dense/BiasAdd",
        ),
    },
    "discogs_effnet": {
        "loader_sr": 16000,
        "graph": "discogs-effnet-bs64-1.pb",
        "builder": lambda pb: TensorflowPredictEffnetDiscogs(
            graphFilename=str(pb),
            output="PartitionedCall:1",
        ),
    },
}


# TF inference

def load_audio_for_embedder(audio_path: Path, sample_rate: int) -> np.ndarray:
    return MonoLoader(
        filename=str(audio_path),
        sampleRate=sample_rate,
        resampleQuality=4,
    )()


def run_embedder(audio_path: Path, models_dir: Path, embedder_name: str) -> np.ndarray:
    spec = EMBEDDER_SPECS[embedder_name]
    graph_path = models_dir / spec["graph"]
    if not graph_path.exists():
        raise FileNotFoundError(f"Missing embedder graph: {graph_path}")
    audio = load_audio_for_embedder(audio_path, spec["loader_sr"])
    embedder = spec["builder"](graph_path)
    return np.array(embedder(audio))


def build_classifier_with_fallbacks(
    classifier_pb: Path,
    input_candidates: List[str],
    output_candidates: List[str],
) -> TensorflowPredict2D:
    errors = []
    for input_name in input_candidates:
        for output_name in output_candidates:
            try:
                return TensorflowPredict2D(
                    graphFilename=str(classifier_pb),
                    input=input_name,
                    output=output_name,
                )
            except RuntimeError as e:
                errors.append(f"input={input_name}, output={output_name}: {e}")
    raise RuntimeError(
        f"Could not configure classifier for {classifier_pb.name}.\n"
        + "\n".join(errors[:8])
    )


def run_classifier(
    embeddings: np.ndarray,
    classifier_pb: Path,
    classifier_input_candidates: Optional[List[str]] = None,
    classifier_output_candidates: Optional[List[str]] = None,
) -> np.ndarray:
    input_candidates = unique_preserve_order(
        (classifier_input_candidates or []) + [
            "model/Placeholder",
            "serving_default_model_Placeholder",
        ]
    )
    output_candidates = unique_preserve_order(
        (classifier_output_candidates or []) + [
            "model/Softmax",
            "model/Sigmoid",
            "PartitionedCall",
            "PartitionedCall:0",
        ]
    )
    model = build_classifier_with_fallbacks(
        classifier_pb=classifier_pb,
        input_candidates=input_candidates,
        output_candidates=output_candidates,
    )
    return aggregate_predictions(model(embeddings))


def run_model_suite(audio_path: Path, models_dir: Path, enabled_models: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    embed_cache: Dict[str, np.ndarray] = {}

    for model_name in enabled_models:
        spec = MODEL_SPECS[model_name]
        embedder_name = spec["embedder"]

        classifier_path = models_dir / spec["classifier_pb"]
        meta_path = models_dir / spec["classifier_meta"]

        if not classifier_path.exists():
            raise FileNotFoundError(f"Missing classifier graph: {classifier_path}")
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing classifier metadata: {meta_path}")

        if embedder_name not in embed_cache:
            embed_cache[embedder_name] = run_embedder(audio_path, models_dir, embedder_name)

        preds = run_classifier(
            embeddings=embed_cache[embedder_name],
            classifier_pb=classifier_path,
            classifier_input_candidates=spec.get("classifier_input_candidates"),
            classifier_output_candidates=spec.get("classifier_output_candidates"),
        )

        labels = extract_class_names_from_metadata(meta_path)
        if not labels:
            raise ValueError(f"Could not extract class labels from metadata: {meta_path}")

        result.update(predictions_to_dict(preds, labels, spec["prefix"]))

    return result


# Aliases + binary cleanup

def add_convenience_aliases(features: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(features)

    danceable_score = pick_score_by_keyword(
        out, prefix="is_danceable_",
        positive_keywords=["danceable"],
        negative_keywords=["not_", "non_", "no_", "notdanceable"],
    )
    if danceable_score is not None:
        out["is_danceable"] = danceable_score

    vocal_score = pick_score_by_keyword(
        out, prefix="voice_instrumental_",
        positive_keywords=["voice", "vocal"],
        negative_keywords=["instrumental", "no_voice", "non_voice"],
    )
    if vocal_score is not None:
        out["is_vocal"] = vocal_score

    female_score = pick_score_by_keyword(
        out, prefix="voice_gender_",
        positive_keywords=["female", "woman", "girl"],
        negative_keywords=["male", "man", "boy"],
    )
    if female_score is not None:
        out["voice_gender_female"] = female_score

    for mood_name, prefix in {
        "happy": "mood_happy_",
        "sad": "mood_sad_",
        "relaxed": "mood_relaxed_",
        "aggressive": "mood_aggressive_",
        "party": "mood_party_",
        "acoustic": "mood_acoustic_",
        "electronic": "mood_electronic_",
    }.items():
        score = pick_score_by_keyword(
            out, prefix=prefix,
            positive_keywords=[mood_name],
            negative_keywords=[f"not_{mood_name}", f"non_{mood_name}"],
        )
        if score is not None:
            out[f"mood_{mood_name}"] = score

    return out


def drop_binary_raw_columns(features: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(features)
    raw_binary_prefixes = [
        "is_danceable_", "voice_instrumental_", "voice_gender_",
        "mood_happy_", "mood_sad_", "mood_relaxed_", "mood_aggressive_",
        "mood_party_", "mood_acoustic_", "mood_electronic_",
    ]
    keys_to_drop = [k for k in out if any(k.startswith(p) for p in raw_binary_prefixes)]
    for k in keys_to_drop:
        out.pop(k)
    return out


# File discovery + per-track extraction

def find_mp3_files(input_root: Path) -> List[Path]:
    return sorted(p for p in input_root.glob("*.mp3") if p.is_file())


def extract_one_file(
    audio_path: Path,
    models_dir: Path,
    enabled_models: List[str],
) -> Dict[str, Any]:
    album, original_filename = split_album_and_filename(audio_path.name)

    row: Dict[str, Any] = {
        "album": album,
        "filename": original_filename,
    }

    row.update(extract_handcrafted_features(audio_path))
    row.update(run_model_suite(audio_path, models_dir, enabled_models))
    row = add_convenience_aliases(row)
    row = drop_binary_raw_columns(row)

    return row


# Main

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Essentia features from a flat folder of MP3s."
    )
    parser.add_argument("--input-root", required=True,
                        help="Flat folder of MP3s, e.g. sample/milonga")
    parser.add_argument("--output-csv", default="essentia_features.csv",
                        help="Output CSV path (default: essentia_features.csv)")
    parser.add_argument("--models-dir", required=True,
                        help="Directory with Essentia .pb / .json model files")
    parser.add_argument("--include-nsynth", action="store_true",
                        help="Also run the nsynth instrument classifier")
    parser.add_argument("--max-files", type=int, default=None,
                        help="Cap the number of files processed (useful for testing)")
    args = parser.parse_args()

    input_root = Path(args.input_root)
    output_csv = Path(args.output_csv)
    models_dir = Path(args.models_dir)

    if not input_root.is_dir():
        raise NotADirectoryError(f"Input root not found or not a directory: {input_root}")
    if not models_dir.is_dir():
        raise NotADirectoryError(f"Models directory not found: {models_dir}")

    enabled_models = [
        "is_danceable", "voice_instrumental", "voice_gender",
        "mood_happy", "mood_sad", "mood_relaxed", "mood_aggressive",
        "mood_party", "mood_acoustic", "mood_electronic",
        "moods_mirex", "mtg_jamendo_top50tags",
    ]
    if args.include_nsynth:
        enabled_models.append("nsynth_instrument")

    mp3_files = find_mp3_files(input_root)
    if not mp3_files:
        raise FileNotFoundError(f"No .mp3 files found under: {input_root}")
    if args.max_files:
        mp3_files = mp3_files[:args.max_files]

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    total = len(mp3_files)

    print(f"Processing {total} MP3 files from: {input_root}")

    for i, audio_path in enumerate(mp3_files, start=1):
        print(f"[{i}/{total}] {audio_path.name}")
        try:
            rows.append(extract_one_file(audio_path, models_dir, enabled_models))
        except Exception as e:
            album, original_filename = split_album_and_filename(audio_path.name)
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
