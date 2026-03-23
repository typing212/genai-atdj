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

- [ ] **README Setup Guide for Media Pool & Preprocessing**
  - *Summary:* Write a complete user-facing setup section in `README.md` covering the offline media pool preparation flow so new users can get started without prior knowledge.
  - *Clarification:* Once all features and files are finalized, `README.md` must include step-by-step instructions for: (1) copying audio files to `data/raw/`, (2) running feature extraction via notebook or CLI, (3) running RAG ingest, and (4) launching the app. Should also mention when steps 2–3 need to be re-run (i.e. when new tracks are added). This is a documentation task — implement at the end of WP-11 or alongside the final reproducibility pass. Tied to the Reproducibility rubric criterion (5%).

- [ ] **User Music Upload & On-the-Fly Feature Extraction**
  - *Summary:* Allow users to upload a new music file at runtime, have it ingested into the track pool, and have audio features extracted immediately — all through the UI.
  - *Clarification:* A stretch goal built on top of existing infrastructure. A file upload widget in Streamlit (WP-02 UI layer) lets the user add a new track. The uploaded file is saved to `data/raw/`, then `extract_features()` from WP-04 is called on-the-fly (it already supports single-track use). The resulting track is appended to `catalog.csv` (WP-01 catalog) and incrementally indexed into ChromaDB (WP-07 RAG) so it becomes immediately available for planning. No external APIs required — fully local. Key implication: ChromaDB ingest must support single-track incremental updates, not just full catalog batch runs. Implement only if time permits after core WPs are stable.

- [ ] **Track Schema & Test Update After WP-02 Extraction**
  - *Summary:* Revisit `Track` schema and its tests once real audio feature extraction reveals what fields are missing.
  - *Clarification:* After WP-02 (librosa/mutagen extraction) runs on the real music pool, new fields may be needed in `atdj/schemas/track.py` that weren't anticipated during WP-01 setup. Both the schema and `tests/test_schemas.py` must be updated together — new fields need corresponding tests for defaults, constraints, and validators. Should happen before WP-03/04 begin consuming `Track` objects downstream.

- [ ] **Convention vs Flexible Planning Mode**
  - *Summary:* Add a user-controlled `planning_mode` field to `MilongaSession` that switches between strict tanda homogeneity rules and agent-overridable conventions.
  - *Clarification:* Style (tango/vals/milonga) remains a hard constraint enforced by Pydantic in all modes. Orchestra, singer, and decade homogeneity move out of Pydantic into a planner-layer validator (`atdj/planner/tanda_rules.py`). In **convention mode** (default), that validator treats mixed orchestra, singer, or decade as hard errors — same behavior as today but at the planner layer. In **flexible mode**, violations are allowed only if the agent supplies a non-empty `rationale` on the `Tanda`; no rationale = blocked. `MilongaSession` gets a new field `planning_mode: Literal["convention", "flexible"] = "convention"`. The UI (WP-08) exposes this as a toggle so the user can switch before starting a session. Implement in WP-05 (planner/validator work package).

- [ ] **Expand FeedbackEvent Types Based on Real Usage**
  - *Summary:* Add new `event_type` values to `FeedbackEvent` as real milonga testing reveals signal types not yet covered.
  - *Clarification:* The current `Literal[...]` list in `atdj/schemas/feedback.py` has 9 fixed values. New human signal types may emerge during testing that require expansion. Any new `event_type` must be added to both the schema and `tests/test_schemas.py`, and the agent routing logic (WP-06) must handle it — schema and agent changes should go together.

- [ ] **Separate Cortina & Tango Music Handling in UI**
  - *Summary:* Ask users to organize cortina and tango files separately, with distinct upload/import flows for each type.
  - *Clarification:* Currently both tango tracks and cortinas go through the same metadata/feature extraction pipeline, but cortinas have many null metadata fields by nature (no orchestra, singer, year, etc.). A cleaner approach: have the UI explicitly ask users to handle cortina and tango imports separately — tango tracks through the full metadata pipeline, cortinas through a simplified flow that only extracts audio features and auto-sets style to "cortina". This would make the catalog cleaner and reduce confusion about null fields.

- [ ] **Media Pool Browser Page**
  - *Summary:* A Streamlit page where the user can browse the music pool as a filterable table showing only human-readable columns.
  - *Clarification:* A new page (`page_media_pool.py`) in the Streamlit UI (WP-10) that reads `catalog.csv` and displays a filtered view with only user-facing columns: title, orchestra, singer, style, year, decade, and duration. Technical extraction fields (bpm, energy, key, danceability, brightness, snr_estimate_db, embedding_id, etc.) are hidden. The table should be filterable by orchestra, style, and decade at minimum. Read-only — no editing. Depends on WP-02 (catalog must be populated with real data first).

