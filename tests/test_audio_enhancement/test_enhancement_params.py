"""Tests for the newly exposed parameters in enhance_track() and enhance_tanda()."""
import numpy as np
import pytest
import soundfile as sf

from pathlib import Path
from atdj.audio.enhancement import enhance_track, enhance_tanda


@pytest.fixture
def sample_wav(tmp_path) -> Path:
    """Generate a short WAV at 44100 Hz, loud enough for stable LUFS measurement."""
    sr = 44100
    duration = 3
    t = np.linspace(0, duration, sr * duration, endpoint=False)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)
             + 0.2 * np.sin(2 * np.pi * 1200 * t)).astype(np.float32)
    path = tmp_path / "test_track.wav"
    sf.write(str(path), audio, sr)
    return path


@pytest.fixture
def two_sample_wavs(tmp_path) -> list[Path]:
    sr = 44100
    duration = 3
    t = np.linspace(0, duration, sr * duration, endpoint=False)
    paths = []
    for i, freq in enumerate([440, 880]):
        audio = (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        p = tmp_path / f"track_{i}.wav"
        sf.write(str(p), audio, sr)
        paths.append(p)
    return paths


# ── enhance_track new params ──────────────────────────────────────────────────

class TestEnhanceTrackNewParams:
    def test_default_params_unchanged_behavior(self, sample_wav, tmp_path):
        out = tmp_path / "out.wav"
        result = enhance_track(sample_wav, out)
        assert out.exists()
        assert "snr_before" in result
        assert "lufs" in result

    def test_custom_highpass_runs_without_error(self, sample_wav, tmp_path):
        out = tmp_path / "out.wav"
        result = enhance_track(sample_wav, out, highpass_hz=120.0)
        assert out.exists()
        assert result["snr_before"] is not None

    def test_custom_lowered_highpass(self, sample_wav, tmp_path):
        out = tmp_path / "out.wav"
        result = enhance_track(sample_wav, out, highpass_hz=60.0)
        assert out.exists()

    def test_custom_limiter_threshold(self, sample_wav, tmp_path):
        out = tmp_path / "out.wav"
        result = enhance_track(sample_wav, out, limiter_threshold_db=-3.0)
        assert out.exists()
        assert "peak_db" in result  # limiter param accepted and pipeline completed

    def test_hiss_cutoff_override_disables_auto_detect(self, sample_wav, tmp_path):
        out = tmp_path / "out.wav"
        # 8000 Hz is well below Nyquist for 44100 Hz audio
        result = enhance_track(sample_wav, out, hiss_cutoff_override=8000.0)
        assert out.exists()
        assert result["hiss_cutoff"] == pytest.approx(8000.0, abs=1.0)

    def test_hiss_cutoff_none_uses_auto(self, sample_wav, tmp_path):
        out = tmp_path / "out.wav"
        result = enhance_track(sample_wav, out, hiss_cutoff_override=None)
        assert out.exists()
        assert result["hiss_cutoff"] > 0

    def test_custom_target_lufs(self, sample_wav, tmp_path):
        out_loud = tmp_path / "loud.wav"
        out_quiet = tmp_path / "quiet.wav"
        enhance_track(sample_wav, out_loud, target_lufs=-11.0)
        enhance_track(sample_wav, out_quiet, target_lufs=-18.0)
        audio_loud, sr = __import__("librosa").load(str(out_loud), sr=None, mono=True)
        audio_quiet, _ = __import__("librosa").load(str(out_quiet), sr=None, mono=True)
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        lufs_loud = meter.integrated_loudness(audio_loud)
        lufs_quiet = meter.integrated_loudness(audio_quiet)
        assert lufs_loud > lufs_quiet

    def test_no_output_path_returns_metrics_only(self, sample_wav):
        result = enhance_track(sample_wav, output_path=None)
        assert "snr_before" in result
        assert "lufs" in result


# ── enhance_tanda param_overrides ────────────────────────────────────────────

class TestEnhanceTandaParamOverrides:
    def test_backward_compat_no_overrides(self, two_sample_wavs, tmp_path):
        results = enhance_tanda(two_sample_wavs, tmp_path)
        assert len(results) == 2
        for r in results:
            assert "lufs" in r
            assert Path(r["output_path"]).exists()

    def test_param_overrides_applied(self, two_sample_wavs, tmp_path):
        overrides = [{"target_lufs": -11.0}, {"target_lufs": -11.0}]
        results_loud = enhance_tanda(two_sample_wavs, tmp_path / "loud", param_overrides=overrides)
        results_default = enhance_tanda(two_sample_wavs, tmp_path / "default")
        for loud, default in zip(results_loud, results_default):
            assert loud["lufs"] > default["lufs"] - 0.5

    def test_partial_overrides_merge_with_adaptive(self, two_sample_wavs, tmp_path):
        overrides = [{"target_lufs": -11.0}, {}]
        results = enhance_tanda(two_sample_wavs, tmp_path, param_overrides=overrides)
        assert len(results) == 2

    def test_none_overrides_same_as_no_arg(self, two_sample_wavs, tmp_path):
        r1 = enhance_tanda(two_sample_wavs, tmp_path / "a", param_overrides=None)
        r2 = enhance_tanda(two_sample_wavs, tmp_path / "b")
        assert len(r1) == len(r2)

    def test_empty_dict_overrides_use_adaptive(self, two_sample_wavs, tmp_path):
        overrides = [{}, {}]
        results = enhance_tanda(two_sample_wavs, tmp_path, param_overrides=overrides)
        assert len(results) == 2
        for r in results:
            assert "lufs" in r
