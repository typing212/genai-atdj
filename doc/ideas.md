# AT-DJ Ideas

Ideas recorded during development. Unchecked = not yet implemented. Checked = done.

---

- [ ] **Feedback Interrupt & Race-to-Deadline Replanning**
  - *Summary:* Feedback always triggers an immediate replan from scratch, raced against a playback deadline with a fallback placeholder.
  - *Clarification:* When feedback arrives at any point (even mid-planning), the system always starts a fresh replan immediately. If a plan B exists in the lookahead buffer, it is used as the placeholder while replanning; if not, the current plan is finished and used as placeholder. Whichever replan finishes before the expected playback start time wins — if the replan is too slow, the placeholder plays instead. This "race against the clock" pattern ensures the system is always responsive and never deadlocks. UI always shows a notification when the next tanda is updated, and user can hit "play next" to jump in immediately. Interactive/demo mode is the primary target — latency is a first-class concern.

- [ ] **Onboarding Mood Calibration Flow**
  - *Summary:* An optional skippable onboarding screen that plays 3 sample tracks and asks the user to pick feeling cards, building a personal reference frame for interpreting their future feedback language.
  - *Clarification:* A new `page_onboarding.py` UI flow shown once at session start (skippable). User listens to 3 carefully chosen tracks spanning the mood/energy spectrum and selects feeling cards (e.g. "Nostalgic", "Electric", "Melancholic") or types their own. These reactions are stored in `AgentState` as few-shot examples. When the user later sends feedback like "more dramatic", the LLM includes their onboarding reactions as few-shot context to interpret what that word means *to this specific user* — since different users mean different things by the same words. Not used to set the energy arc. Low priority — implement only if time permits after WP-08.

- [ ] **Settings Page for LLM API Key**
  - *Summary:* Add a Settings page where users can input their own LLM API key at runtime without needing a pre-configured `.env` file.
  - *Clarification:* A new 5th Streamlit page (`page_settings.py`) with a text input for the API key (Anthropic, Groq, etc.). The key is stored in `st.session_state` for the session only — not persisted to disk. `atdj/config.py` must be updated to support runtime key injection as a fallback over the env var, and the LangGraph agent must be re-initialized when the key changes. Relevant in WP-08 (Streamlit UI).

