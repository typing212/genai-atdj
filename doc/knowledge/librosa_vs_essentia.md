# Librosa vs Essentia for Music Feature Extraction

## Answer Summary
Librosa is a pure-Python MIR library — cross-platform, widely used in research, but slower for large batches. Essentia is a C++ library from MTG Barcelona with higher-level, production-tested algorithms and broader feature coverage (including a dedicated `Danceability` descriptor and a more robust rhythm extractor), but has no Windows wheel on PyPI. For AT-DJ, librosa is the practical choice on Windows; Essentia would be preferable on Linux for batch extraction speed and tango-relevant descriptors.

## Key Takeaways
- Librosa: pure Python, works on all platforms, sufficient feature coverage, slower on large catalogs
- Essentia: C++ bindings, 3–5× faster, richer descriptors (`Danceability`, `RhythmExtractor2013`, `KeyExtractor`), Linux/macOS only
- For BPM: both work; Essentia's `RhythmExtractor2013` is more robust on complex/dance rhythms
- For key detection: Essentia's `KeyExtractor` (Krumhansl-Schmuckler) is more musicologically grounded than librosa's chroma argmax
- For danceability: Essentia has a dedicated `Danceability` algorithm; librosa requires a hand-crafted composite score
- Essentia's `Danceability` and rhythm descriptors are particularly relevant to tango, which has strong but sometimes syncopated rhythmic structure
- Feature selection for AT-DJ is deferred until the agent feedback loop reveals which descriptors actually drive good tanda planning decisions

## Relevance to AT-DJ Paper
The choice of librosa over essentia can be cited in the methodology section as a practical infrastructure decision (Windows compatibility), with a note that essentia's `Danceability` and `RhythmExtractor2013` would be preferable in a production Linux deployment. The deferred feature selection approach — waiting for the agent feedback loop to reveal which features matter — is itself a design decision worth mentioning as it avoids premature optimization of the feature engineering layer.
