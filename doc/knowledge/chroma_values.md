# Chroma Values in Audio Feature Extraction

## Answer Summary
A chroma value measures the energy present at each of the 12 pitch classes (C through B) in a frame of audio, collapsing all octaves into a single musically-meaningful bin. Librosa computes these using a Constant-Q Transform (CQT), whose frequency bands are logarithmically spaced to align with musical notes. Averaging chroma across all frames of a track yields a 12-dimensional profile that characterizes which pitch classes dominate the piece — the basis for key estimation.

## Key Takeaways
- There are exactly 12 chroma bins, one per semitone in the Western octave (C, C#, D, … B).
- Chroma is **octave-invariant**: a C played in any octave contributes to the same C bin.
- Chroma is **timbre-invariant**: it captures *which notes* are played, not *how* they sound.
- `argmax(chroma_mean)` gives the dominant pitch class — a fast but rough key estimate that cannot distinguish major from minor.
- Essentia's `KeyExtractor` improves on this by returning both key and scale (major/minor), which matters for tango since golden-age repertoire is predominantly minor-mode.
- **Chroma distance** (cosine or L2) between two tracks is a proxy for harmonic compatibility — useful for grouping tracks into tandas.

## Relevance to AT-DJ Paper
Chroma-based key estimation is the acoustic foundation for harmonic tanda planning; the paper can cite it when justifying why tracks in harmonically related keys are grouped together, and contrast librosa's argmax approach with essentia's scale-aware `KeyExtractor` as a motivating example of feature quality trade-offs.
