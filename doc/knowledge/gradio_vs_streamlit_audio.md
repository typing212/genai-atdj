# Gradio vs Streamlit — Audio Playback and Python-First UI

## Answer Summary
Both Gradio and Streamlit are 100% Python with no HTML/JS required. Gradio has first-class audio support — built-in waveform rendering, native before/after comparison layouts, microphone input, and streaming audio output — making it significantly better than Streamlit's basic `st.audio()` wrapper for audio-heavy features. Streamlit is stronger for multi-page apps, flexible layouts, and table-heavy interfaces. For AT-DJ, Streamlit suits the session console and catalog pages while Gradio is the better fit for the Audio Workbench (before/after enhancement comparison).

## Key Takeaways
- Both frameworks are pure Python — no frontend code required
- Streamlit audio = `st.audio()` only: basic browser player, no waveform, no reactivity, no recording
- Gradio audio = `gr.Audio`: built-in waveform display, upload→process→play pipeline, mic recording, `streaming=True`, `autoplay=True`
- Gradio's native before/after audio layout requires zero extra code; Streamlit requires manual matplotlib + st.audio hacking
- Streamlit is stronger for: multi-page navigation, `st.session_state`, AgGrid tables, Plotly charts, layout flexibility
- Gradio is stronger for: audio/image ML demos, upload→inference→output pipelines, streaming outputs
- Gradio can be mounted inside FastAPI via `gr.mount_gradio_app()` — possible to combine both in one app but adds complexity
- **Recommended decision point**: if Audio Workbench is a primary demo feature → Gradio; if session console + catalog table matter more → Streamlit

## Relevance to AT-DJ Paper
The UI framework choice can be justified in the Implementation section by citing Gradio's native audio pipeline support as the deciding factor if audio enhancement is foregrounded in the demo, or Streamlit's multi-page session state management if the live DJ console is the primary showcase.
