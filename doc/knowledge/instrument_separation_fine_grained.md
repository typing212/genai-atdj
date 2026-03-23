# Fine-Grained Instrument Separation for Tango

## Answer Summary
Standard 4-stem Demucs collapses bandoneon, violin, and piano into a single `other` stem because it was trained on pop/rock data (MUSDB18), not tango. A 6-stem Demucs variant adds a piano stem but still has no bandoneon or violin. The most practical path for tango-specific instrument separation without labeled training data is **AudioSep**, a zero-shot model that separates any instrument described in natural language (e.g., "the bandoneon in this tango recording").

## Key Takeaways
- Demucs `htdemucs` (4-stem): vocals / drums / bass / other — bandoneon + violin + piano all land in `other`.
- Demucs `htdemucs_6s` (6-stem): adds `guitar` and `piano` stems — piano is directly useful for tango; still no bandoneon or violin.
- **AudioSep** (NeurIPS 2023): zero-shot language-guided separation — query `"bandoneon"` or `"violin section"` with no retraining needed; quality is lower than supervised models but currently the only feasible path for bandoneon.
- Fine-tuning Demucs on tango would give the best results but requires multi-track tango recordings — almost no public dataset exists for this.
- NMF (Non-negative Matrix Factorization) can roughly decompose tango spectrograms into instrument components without training data, useful for exploratory notebooks.
- Golden-age tango's limited palette (~4 instruments) actually makes it a favorable target for fine-tuning if training data can be obtained.

## Relevance to AT-DJ Paper
The paper can cite the gap between pop-trained source separation models and tango's unique instrumentation as a domain adaptation challenge, and position AudioSep zero-shot querying as a pragmatic workaround; fine-tuning on tango multi-tracks can be framed as a meaningful future work direction.
