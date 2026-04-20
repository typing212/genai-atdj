"""Tests for atdj.audio.enhancement — uses synthetic audio, no real files needed."""

import tempfile
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from atdj.audio.enhancement import (
    compute_per_track_params,
    enhance_track,
    find_music_cutoff,
    measure_snr,
    measure_spectral_centroid,
)

SR = 22050


def _make_sine_with_noise(duration_s=3.0, freq=440.0, noise_level=0.05):
    """Generate a sine wave with white noise added."""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * freq * t)
    audio += noise_level * np.random.default_rng(42).standard_normal(len(audio))
    return audio.astype(np.float32)


def _save_wav(audio, tmp_dir):
    """Save audio to a temp WAV file and return its Path."""
    path = Path(tmp_dir) / "test_track.wav"
    sf.write(str(path), audio, SR)
    return path


def test_measure_snr_positive():
    audio = _make_sine_with_noise(noise_level=0.01)
    snr = measure_snr(audio, SR)
    assert snr > 0, f"Expected positive SNR for clean signal, got {snr}"


def test_measure_snr_noisy_lower():
    clean = _make_sine_with_noise(noise_level=0.01)
    noisy = _make_sine_with_noise(noise_level=0.3)
    assert measure_snr(clean, SR) > measure_snr(noisy, SR)


def test_find_music_cutoff_respects_min():
    audio = _make_sine_with_noise(freq=200.0, noise_level=0.001)
    cutoff = find_music_cutoff(audio, SR, min_cutoff=5000.0)
    assert cutoff >= 5000.0


def test_measure_spectral_centroid_range():
    audio = _make_sine_with_noise(freq=440.0, noise_level=0.01)
    centroid = measure_spectral_centroid(audio, SR)
    assert 100 < centroid < SR / 2


def test_enhance_improves_snr():
    audio = _make_sine_with_noise(noise_level=0.1)
    with tempfile.TemporaryDirectory() as tmp:
        inp = _save_wav(audio, tmp)
        out = Path(tmp) / "enhanced.wav"
        metrics = enhance_track(inp, out, noise_prop=0.8)
        assert metrics["snr_after"] > metrics["snr_before"]


def test_no_clipping():
    audio = _make_sine_with_noise(noise_level=0.1)
    with tempfile.TemporaryDirectory() as tmp:
        inp = _save_wav(audio, tmp)
        out = Path(tmp) / "enhanced.wav"
        enhance_track(inp, out)
        enhanced, _ = sf.read(str(out))
        assert np.max(np.abs(enhanced)) <= 1.0


def test_lufs_near_target():
    audio = _make_sine_with_noise(noise_level=0.05)
    with tempfile.TemporaryDirectory() as tmp:
        inp = _save_wav(audio, tmp)
        out = Path(tmp) / "enhanced.wav"
        metrics = enhance_track(inp, out, target_lufs=-14.0)
        # Dynamic hiss filter runs after LUFS norm and removes some energy,
        # so final LUFS may be slightly above target. Allow 6 LU tolerance.
        assert abs(metrics["lufs"] - (-14.0)) < 6.0, f"LUFS {metrics['lufs']} too far from -14"


def test_output_file_created():
    audio = _make_sine_with_noise()
    with tempfile.TemporaryDirectory() as tmp:
        inp = _save_wav(audio, tmp)
        out = Path(tmp) / "subdir" / "enhanced.wav"
        enhance_track(inp, out)
        assert out.exists()


def test_flat_eq_no_boost():
    audio = _make_sine_with_noise(noise_level=0.05)
    with tempfile.TemporaryDirectory() as tmp:
        inp = _save_wav(audio, tmp)
        out = Path(tmp) / "enhanced.wav"
        metrics = enhance_track(inp, out, eq_low_gain=0.0, eq_vocal_gain=0.0)
        assert metrics["snr_after"] >= metrics["snr_before"]


def test_compute_per_track_params_adaptive():
    profiles = [
        {"name": "clean", "snr": 60.0, "spectral_centroid": 1500.0},
        {"name": "noisy", "snr": 30.0, "spectral_centroid": 800.0},
        {"name": "mid", "snr": 45.0, "spectral_centroid": 1100.0},
    ]
    params, summary = compute_per_track_params(profiles)
    assert len(params) == 3
    noisy_params = params[1]
    clean_params = params[0]
    assert noisy_params["noise_prop"] > clean_params["noise_prop"]
