# Instrument Identification from Audio Features

## Answer Summary
Instruments cannot be reliably identified from track-level features like chroma or averaged MFCCs alone, because these mix all instruments together. Identifying instruments requires either source separation (e.g., Demucs) followed by per-stem classification, or an end-to-end multi-label classifier trained on labeled audio. For tango specifically, the instrument palette is small and consistent (bandoneon, violin, piano, bass, optional voice), making targeted identification more tractable than general music.

## Key Takeaways
- **MFCCs** are the best proxy in the current notebook — they encode timbre — but track-averaged MFCCs conflate all instruments.
- **Chroma** captures pitch content, not timbre, so it offers little direct instrument signal.
- **Source separation first** (e.g., Demucs 4-stem) is the standard approach: isolate stems, then classify each.
- **CLAP zero-shot** (e.g., query `"tango with singer"`) is a low-cost alternative requiring no labeled training data.
- Tango orquesta instrumentation is narrow (~5 instrument classes), making few-shot or fine-tuned classifiers very feasible.
- **Vocal/instrumental** detection is the highest-value signal for tanda planning and is partially encoded in ID3 tags already — audio-derived confirmation would be more reliable.
- OpenMIC-2018 and MedleyDB are standard datasets for instrument presence classification if training is needed.

## Relevance to AT-DJ Paper
The paper can discuss instrument identification as a future feature dimension — specifically vocal vs. instrumental detection via source separation — and cite CLAP or Demucs as lightweight paths that avoid the need for labeled tango-specific training data.
