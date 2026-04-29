"""Audio enhancement pipeline for old tango recordings.

Pipeline order: noise reduction → EQ → LUFS norm → limiter → dynamic hiss filter.
Adaptive parameters (noise_prop, eq gains) are computed per-track based on tanda analysis.
Fixed parameters (highpass, LUFS target, limiter threshold) never change.
"""

from pathlib import Path

import librosa
import noisereduce as nr
import numpy as np
import pedalboard
import pyloudnorm as pyln
import soundfile as sf


def measure_snr(audio: np.ndarray, sr: int) -> float:
    """Estimate SNR by comparing energy in signal band (200-4000Hz) vs noise band (8000-16000Hz)."""
    n_fft = 2048
    S = np.abs(librosa.stft(audio, n_fft=n_fft))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    sig_mask = (freqs >= 200) & (freqs <= 4000)
    sig_energy = np.mean(S[sig_mask, :] ** 2)

    noise_mask = (freqs >= 8000) & (freqs <= min(16000, sr // 2))
    if not noise_mask.any():
        return float("inf")
    noise_energy = np.mean(S[noise_mask, :] ** 2)

    if noise_energy == 0:
        return float("inf")
    return float(10 * np.log10(sig_energy / noise_energy))


def find_music_cutoff(audio: np.ndarray, sr: int, threshold_db: float = -40,
                      min_cutoff: float = 5000.0) -> float:
    """Find the frequency where musical energy drops off.

    Walks from high frequencies downward until energy rises above threshold_db
    relative to the loudest frequency. Returns the cutoff frequency in Hz.
    """
    n_fft = 2048
    S = np.abs(librosa.stft(audio, n_fft=n_fft))
    avg_spectrum = np.mean(S, axis=1)
    avg_db = 20 * np.log10(avg_spectrum + 1e-10)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    peak_db = avg_db.max()

    for i in range(len(freqs) - 1, -1, -1):
        if avg_db[i] > (peak_db + threshold_db):
            cutoff = min(freqs[i] + 500, sr // 2)
            return max(cutoff, min_cutoff)

    return min_cutoff


def measure_spectral_centroid(audio: np.ndarray, sr: int) -> float:
    """Spectral centroid = "center of mass" of the frequency spectrum (Hz).

    Higher = brighter/thinner, lower = warmer/darker.
    """
    centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
    return float(np.mean(centroid))


def analyze_tanda_tracks(track_paths: list[Path]) -> list[dict]:
    """Measure audio profiles for a group of tracks.

    Returns a list of dicts with: path, name, snr, lufs, spectral_centroid, sr.
    """
    profiles = []
    for tp in track_paths:
        audio, sr = librosa.load(str(tp), sr=None, mono=True)
        meter = pyln.Meter(sr)
        profiles.append({
            "path": tp,
            "name": tp.stem,
            "snr": measure_snr(audio, sr),
            "lufs": meter.integrated_loudness(audio),
            "spectral_centroid": measure_spectral_centroid(audio, sr),
            "sr": sr,
        })
    return profiles


def compute_per_track_params(profiles: list[dict]) -> tuple[list[dict], dict]:
    """Derive per-track enhancement parameters from tanda analysis.

    Returns (params_list, tanda_summary).
    """
    snrs = [p["snr"] for p in profiles]
    centroids = [p["spectral_centroid"] for p in profiles]

    median_snr = float(np.median(snrs))
    median_centroid = float(np.median(centroids))
    snr_range = max(float(np.ptp(snrs)), 1.0)
    centroid_range = max(float(np.ptp(centroids)), 1.0)

    params_list = []
    for p in profiles:
        noise_prop = float(np.clip(0.2 + 0.5 * (median_snr - p["snr"]) / snr_range, 0.2, 0.8))
        centroid_offset = (p["spectral_centroid"] - median_centroid) / centroid_range
        eq_low_gain = float(np.clip(2.0 + 1.5 * centroid_offset, 0.0, 3.5))
        eq_vocal_gain = float(np.clip(1.5 - 1.5 * centroid_offset, 0.0, 3.5))

        params_list.append({
            "name": p["name"],
            "noise_prop": round(noise_prop, 3),
            "eq_low_gain": round(eq_low_gain, 2),
            "eq_vocal_gain": round(eq_vocal_gain, 2),
            "target_lufs": -14.0,
        })

    tanda_summary = {
        "median_snr": round(median_snr, 1),
        "median_centroid": round(median_centroid, 1),
        "snr_range": round(snr_range, 1),
        "centroid_range": round(centroid_range, 1),
    }
    return params_list, tanda_summary


def enhance_track(input_path: Path, output_path: Path | None = None, *,
                  noise_prop: float = 0.5,
                  eq_low_gain: float = 2.0,
                  eq_vocal_gain: float = 1.5,
                  target_lufs: float = -14.0,
                  highpass_hz: float = 80.0,
                  limiter_threshold_db: float = -1.0,
                  hiss_cutoff_override: float | None = None) -> dict:
    """Enhance a single track through the full pipeline.

    Pipeline: noise reduction → EQ → LUFS norm → limiter → dynamic hiss filter.
    Returns a metrics dict.
    """
    audio, sr = librosa.load(str(input_path), sr=None, mono=True)
    snr_before = measure_snr(audio, sr)
    centroid_before = measure_spectral_centroid(audio, sr)
    hiss_cutoff = hiss_cutoff_override if hiss_cutoff_override is not None else find_music_cutoff(audio, sr)

    # Noise reduction
    audio = nr.reduce_noise(y=audio, sr=sr, prop_decrease=noise_prop, stationary=True)

    # EQ
    board_eq = pedalboard.Pedalboard([
        pedalboard.HighpassFilter(cutoff_frequency_hz=highpass_hz),
        pedalboard.LowShelfFilter(cutoff_frequency_hz=800.0, gain_db=eq_low_gain),
        pedalboard.PeakFilter(cutoff_frequency_hz=2000.0, gain_db=eq_vocal_gain, q=0.7),
    ])
    audio = board_eq(audio.astype(np.float32).reshape(1, -1), sr).flatten()

    # LUFS normalization
    meter = pyln.Meter(sr)
    current_lufs = meter.integrated_loudness(audio)
    audio = pyln.normalize.loudness(audio, current_lufs, target_lufs)

    # Limiter + dynamic hiss filter (3x stacked for steep rolloff)
    board_final = pedalboard.Pedalboard([
        pedalboard.Limiter(threshold_db=limiter_threshold_db),
        pedalboard.LowpassFilter(cutoff_frequency_hz=hiss_cutoff),
        pedalboard.LowpassFilter(cutoff_frequency_hz=hiss_cutoff),
        pedalboard.LowpassFilter(cutoff_frequency_hz=hiss_cutoff),
    ])
    audio = board_final(audio.astype(np.float32).reshape(1, -1), sr).flatten()
    audio = np.clip(audio, -1.0, 1.0)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, sr)

    snr_after = measure_snr(audio, sr)
    centroid_after = measure_spectral_centroid(audio, sr)
    final_lufs = meter.integrated_loudness(audio)
    peak_db = float(20 * np.log10(np.max(np.abs(audio)) + 1e-10))

    return {
        "snr_before": snr_before,
        "snr_after": snr_after,
        "snr_delta": snr_after - snr_before,
        "lufs": final_lufs,
        "peak_db": peak_db,
        "centroid_before": centroid_before,
        "centroid_after": centroid_after,
        "hiss_cutoff": hiss_cutoff,
    }


def enhance_tanda(track_paths: list[Path], output_dir: Path,
                  param_overrides: list[dict] | None = None) -> list[dict]:
    """Adaptive enhancement for a group of tracks.

    Analyzes all tracks first, computes per-track adaptive params, then enhances each.
    param_overrides is an optional per-track list of dicts whose keys override the
    adaptive params (e.g. {"target_lufs": -12.5}). None or empty dict means fully adaptive.
    Returns a list of metrics dicts (one per track).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profiles = analyze_tanda_tracks(track_paths)
    params_list, _ = compute_per_track_params(profiles)
    padded = param_overrides if param_overrides else [{} for _ in track_paths]

    results = []
    for profile, auto_params, overrides in zip(profiles, params_list, padded):
        final_params = {**auto_params, **(overrides or {})}
        out_path = output_dir / (profile["name"] + "_enhanced.wav")
        metrics = enhance_track(
            profile["path"],
            out_path,
            noise_prop=final_params["noise_prop"],
            eq_low_gain=final_params["eq_low_gain"],
            eq_vocal_gain=final_params["eq_vocal_gain"],
            target_lufs=final_params.get("target_lufs", -14.0),
            highpass_hz=final_params.get("highpass_hz", 80.0),
            limiter_threshold_db=final_params.get("limiter_threshold_db", -1.0),
            hiss_cutoff_override=final_params.get("hiss_cutoff_override"),
        )
        metrics["name"] = profile["name"]
        metrics["output_path"] = str(out_path)
        results.append(metrics)

    return results
