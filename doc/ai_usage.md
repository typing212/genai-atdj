# Generative AI Usage Log

This document records all Generative AI tools used to **develop** this project (code generation, planning, refactoring), per course requirements on transparency.

---

## Tool & Settings

| Detail | Value |
|---|---|
| **Tool** | [Claude Code](https://claude.ai/claude-code) (Anthropic's agentic coding CLI) |
| **Model** | Claude Opus 4 (`claude-opus-4`) |
| **Interface** | CLI terminal + VS Code integration |
| **Settings** | Default Claude Code settings; no custom temperature or sampling parameters (Claude Code does not expose these) |
| **Project config** | `.claude/settings.json` — hooks for `.env` protection and file-scope guardrails; custom slash commands (`/knowledge`, `/idea`) for research and idea logging |

---

## Prompt Log

Each entry below documents: the key prompt, what it generated, and whether manual edits were made afterward.

---

### 1. Project Blueprint (`doc/BLUEPRINT.md`)

**Prompt (reconstructed):**
> I'm building a course project for a GenAI class. The project is an AI-powered Argentine Tango DJ system. It should use LangGraph agents, ChromaDB for RAG, audio feature extraction, and a Streamlit UI. We have 5 weeks, 3 team members, and need to demo it live. Generate a comprehensive project blueprint with work packages, timeline, dependency map, schemas, and implementation details for each module.

**Generated:** `doc/BLUEPRINT.md` — full project blueprint (~50KB) covering architecture, work packages WP-01 through WP-11, schemas, dependency map, and timeline.

**Manual edits:** Yes — manually edited afterward and continues to be adjusted throughout development as plans evolve. This is a living document.

---

### 2. DJ Console Static UI (`atdj/ui/`)

**Prompt:**
> Build the WP-03 static UI wireframe for the DJ console using Streamlit. It should be a single-page dashboard with: a sidebar for session history and settings, a main area split into Agent Chat, Music Center (now playing + playlist queue), and Agent Log panels, and a bottom section for library browsing, queue management, and file upload. Use the design system colors and follow the blueprint layout. Include stub data for now-playing, queue, and playlist so we can see the layout without a backend.

**Generated:** `atdj/ui/app.py`, `atdj/ui/page_main.py`, `atdj/ui/DESIGN_SYSTEM.md`

**Manual edits:** Followed by iterative Claude Code sessions for minor UI tuning (layout adjustments, styling, stub data changes). These minor follow-up prompts are not individually recorded.

---

### 3. Notebook Restructuring in WP02(`notebooks/02a` through `02e`)

**Prompt:**
> We have a single large exploration notebook for WP-02. Split it into separate focused notebooks: 02a for data prep and feature catalog, 02b for Method 1 (CLAP), 02c for Method 2 (CoT LLM with both 2A and 2B variants), 02d for Method 3 (small model), and 02e for comparison analysis. Each notebook should load shared artifacts from 02a instead of recomputing everything. Keep the same code logic but organize it cleanly with proper save/load between notebooks.

**Generated:** `notebooks/02a_data_feature_prep.ipynb`, `notebooks/02b_method1_clap.ipynb`, `notebooks/02c_method2_cot_llm.ipynb`, `notebooks/02d_method3_small_model.ipynb`, `notebooks/02e_comparison_analysis.ipynb`

**Manual edits:** Yes.

---

### 4. EDA Visualizations in 02a (`notebooks/02a_data_feature_prep.ipynb`)

**Prompt:**
> Improve the EDA analysis in notebook 02a to use charts instead of text-only output. For missing values, show how many each feature has. For variance, add a cumulative chart sorted by variance so I can identify a good cutoff point for selecting the top-k highest-variance features. For correlation, keep the heatmap but also add a ranked bar chart of the most correlated feature pairs to support better visualization and decision-making.

**Generated:** Rewrote Section 2 (Feature EDA) into four chart-based cells: (2a) missing-value bar chart color-coded by severity, (2b) side-by-side individual + cumulative variance plots with 80/90/95% threshold markers, (2c) ranked correlation pairs bar chart, (2d) clustered correlation heatmap.

**Manual edits:** Yes.

### 5. Tanda & Session Constraint Layer (`notebooks/_patch_tanda_session.ipynb`)

**Prompt:**
> Currently we are just letting the LLM choose songs without limitation on the tandas rule (same orchestra+singer, similar decades) and whole session rules (same orchestra+singer won't repeat). These are hard rules unless the user wants to break them. I want to connect this with the existing scoring pipeline. Should we add another LLM call before feature selection to choose orchestra+singer, or is there a better approach?

**Claude's design recommendation (adopted):** Score all songs first with the existing methods, then apply tanda/session rules as a deterministic post-filter — no extra LLM call needed. Orchestra+singer grouping and session tracking are business logic, not musical interpretation.

**Generated:** `notebooks/_patch_tanda_session.ipynb` — `SessionTracker` class and `build_tanda()` function that plugs into any method's scoring output. Groups candidates by (orchestra, singer), filters by session history, enforces decade consistency, and picks the best available group.

**Manual edits:** Yes, integrate the patch notebook into main method notebooks.


### 6. WP-04 Playback UI Polish (`atdj/ui/page_main.py`, `atdj/ui/audio_player.py`)

**Prompt (consolidated from multi-round iterative session):**

The following sub-prompts were given across several rounds:

> 1. Replace the native Streamlit audio player with a custom one. It should autoplay, fade in at the start, cut off cortinas at the configured time limit, and automatically advance to the next track when done.
>
> 2. Make the "Agent Chat" title look the same as the other section headers like "Now Playing" and "Energy Arc", same size, font, color, and capitalization.
>
> 3. The "Transition" label next to the progress bar shouldn't look like a section title. Make it look the same as the other settings labels like Quality Enhance and Cortina.
>
> 4. Put the "Transition" label and its progress bar on the same row as the previous/next buttons, with the label on the left and the bar on the right.
>
> 5. Add a vertical divider line between the next button and the transition elements to visually separate them.
>
> 6. Rename "Gap (s)" to "Transition (s)" since that's more consistent with the rest of the UI.
>
> 7. The audio player, buttons, transition bar, and settings should be the same height as the Now Playing card. There's too much empty space in between, align them to the bottom of the card.
>
> 8. Add a horizontal divider between the Now Playing section and the Energy Arc section, like the one between Energy Arc and Full Playlist.
>
> 9. The search result rows are too tall compared to the playlist rows. Make them more compact so each row takes about the same height as a playlist row.
>
> 10. There's no spacing between the Now Playing card and the controls on its right. Fix whatever is blocking the gap from showing up.
>
> 11. When the audio file is missing, auto-skip to the next track after the transition. But also keep the previous/next buttons working so the user can skip manually without waiting.

**Generated:** `atdj/ui/audio_player.py` (custom audio component), extensive modifications to `atdj/ui/page_main.py` (layout, CSS, controls, search).

**Manual edits:** Yes — multiple rounds of iterative refinement with visual inspection.

---

*Entries below this line are added as development continues.*

---

### 7. Audio Adjustment Subgraph for Chat-Driven Enhancement (`atdj/audio/adjustment_graph.py`, `atdj/ui/page_main.py`)

**Prompt (consolidated from multi-round iterative session):**

> 1. Right now the audio enhancement only runs in batch from a toggle. I want the user to adjust audio through chat instead. They should be able to type things like "make it louder" or "the bass is too heavy" and the agent should figure out what they mean and apply it. Build a small LangGraph for this and wire it into the chat classifier so messages get routed to it.
>
> 2. Use one LLM call to parse the user message into structured fields. The fields are feature, direction, magnitude, and scope. Feature can be loudness, bass, presence, noise, highpass, or limiter. Direction can be up, down, or reset. Magnitude can be small, medium, or large. Scope can be current, next song, next tanda, rest, or specific. Return JSON.
>
> 3. The user is listening to the current song while they ask. Treat the current track as the reference and apply the change to the upcoming tracks only. Do not modify what is already playing.
>
> 4. After parsing, measure the parameters of the current track, compute a relative adjustment for each target track, and run the existing enhance_tanda function with the new parameters. Hand the reply back to the chat panel with one short confirmation line.

**Generated:** `atdj/audio/adjustment_graph.py` — a new LangGraph with parse_request, resolve_targets, measure_reference, compute_adjustments, execute_enhancement, and format_reply nodes. Wiring in `atdj/ui/page_main.py` so the classifier routes ADJUST_AUDIO messages into this graph.

**Manual edits:** Yes — adjusted the parse_request prompt several times to fix scope edge cases, tuned the magnitude delta values after listening to the result, and reworded the confirmation messages so they read naturally.

---

### 8. Current Track Read-Only Rejection Menu (`atdj/audio/adjustment_graph.py`)

**Prompt:**

> When the user asks to change the current song, the agent should not touch it. Instead show a short menu with three options. The first option is apply to all songs after this one. The second option is apply to the next tanda only. The third option is cancel. If the user replies with the option text or just the number, carry forward what they originally asked for and apply it to the new scope. Make sure both "1" and "next tanda" work as a reply.

**Generated:** `reject_current` node and `resolve_pending_menu` entry node in `atdj/audio/adjustment_graph.py`. Added the rejection_options field on the state and the heuristic substring matching that resolves a menu pick into a new scope before re-entering the graph.

**Manual edits:** Yes — added a guard so an off-topic message during a pending menu (for example "plan a Demare tanda" mid-clarification) drops the menu and goes back through the classifier instead of being treated as a menu pick.

---

### 9. Session Log Redesign with Summary Entries (`atdj/agent/nodes.py`, `atdj/audio/adjustment_graph.py`, `atdj/ui/page_main.py`)

**Prompt:**

> The session log shows too many lines for one user request. The user only needs one line that says what happened. Add a summary flag on each log entry. The on-screen log should show only the summary entries. The JSON log file should still keep every detail so we can debug later. Also add a small icon at the start of each line so the user can tell at a glance whether it is a planning entry, an audio entry, or something the user did.

**Generated:** Added `summary: bool` to the `_log` helper in both `atdj/agent/nodes.py` and `atdj/audio/adjustment_graph.py`. Marked one user-facing line per logical event in every node. Updated the Session Log panel in `page_main.py` to filter by the summary flag and added the icon prefixes (📋 PLAN, 🎛 AUDIO, 👤 You).

**Manual edits:** Yes — reworded each summary message a few times to read naturally (for example "Plan complete — 2 tandas ready" instead of the previous "K of N succeeded"), and added a colour key so warnings and errors are easy to spot.

---

### 10. Cortina Propagation Through Agent State (`atdj/agent/state.py`, `atdj/agent/nodes.py`, `atdj/ui/page_main.py`)

**Prompt:**

> The Full Playlist always shows "Cortina" as the title for cortina rows even though the agent picks a real cortina file underneath. The displayed title and the file that actually plays do not match. Add a list field on the agent state that the cortina_selector node appends to. The UI should read the list in order and show the real cortina filename for each row, so the displayed title equals what the user will hear.

**Generated:** New `selected_cortinas: Annotated[list[dict], operator.add]` field in `atdj/agent/state.py`. Updated `cortina_selector` in `nodes.py` to append a dict per selection. Updated `page_main.py` to read the list in order and pass each filename through the existing cortina resolver before display.

**Manual edits:** Yes — fixed the initial state so the list starts empty on every fresh PLAN run, and reset it on Clear so a new plan does not read stale entries from a previous run.

---

### 11. Audio Settings Sliders That Do Not Interrupt Playback (`atdj/ui/page_main.py`, `atdj/ui/audio_player.py`)

**Prompt:**

> When the user moves the Transition slider or the Cortina slider while a song is playing, the audio cuts out and restarts from the beginning. Move these sliders into a Streamlit fragment so the rest of the page does not rerun. The new value should still take effect on the next track to track transition or the next cortina cut-off, but it should not touch the song that is currently playing.

**Generated:** Wrapped the slider section in a `@st.fragment`. Exposed the live values to the audio iframe through `window.__atdjGapMs` and `window.__atdjCortinaSec`. Changed the audio player so it reads these values from the window at advance time instead of baking them in when the iframe first renders.

**Manual edits:** Yes — added a small toast that confirms the new value, because the Session Log entry does not paint until the next full rerun and the user would otherwise have no visible feedback inside the fragment.

---

### 12. LangGraph Learning & Code Structure

**Prompt (reconstructed):**
> I'm trying to understand how LangGraph StateGraph works and how to structure the PLAN subgraph for this project. Can you explain the key concepts (nodes, edges, conditional routing, reducers) and help me set up the graph skeleton with the correct state type?

**Generated:** Explanations of StateGraph mechanics, reducer patterns (`operator.add`), and conditional edge routing. Helped structure the `AgentState` TypedDict and the skeleton of `atdj/agent/graph.py`, including node registration and conditional edge wiring.

**Manual edits:** Yes — adapted the generated structure to fit the project's specific nodes (`session_init`, `tanda_planner`,
`cortina_selector`, `queue_publisher`, etc.) and tuned the conditional routing logic.

---

### 13. Cortina Pool & Generation Pipeline

**Prompt (reconstructed):**
> Help me understand and structure the cortina module — how to score pool clips against a preceding tanda, and how to go from tanda features to a Lyria-generated audio clip via an LLM-crafted prompt.

**Generated:** Explained the scoring formula and feature extraction approach. Helped structure `atdj/cortina/pool.py` (BPM/energy scoring, exclusion list, fallback) and `atdj/cortina/generator.py` (`_summarize_tanda`, `_craft_music_prompt`, `_call_lyria` streaming pipeline).

**Manual edits:** Yes — tuned the scoring weights, mood lookup table, genre list in the prompt rules, and the energy bucketing thresholds.

### 14. UI Bug Fixes (Iterative)

**Prompt (reconstructed, multiple sessions):**
> Various small UI bug reports, e.g.: "the session log is not showing all logs", "the energy arc dots don't update after Clear", "the chat input doesn't clear on send", "Now Playing card doesn't update when a new plan runs after Clear".

**Generated:** Targeted fixes across `atdj/ui/page_main.py` and `atdj/ui/audio_player.py` — session state resets, rerun triggers, widget key corrections, and DOM/iframe timing patches.

**Manual edits:** Yes — each fix was verified manually in the browser before keeping; several required follow-up prompts when the first generated fix introduced a regression elsewhere.

---

### 15. Project Report Writing Assistance

**Prompt (reconstructed):**
> Help us write the structure of the AT-DJ project report based on the actual source code. Help us check the grammar and fix the logic of our overall writing. 

**Generated:** LaTeX structure content for all sections, including figures, tables, and prose grounded in the actual implementation. Grammar and logic suggestions. 

**Manual edits:** Yes — wrote based on the structure and reviewed all generated content against the source code, corrected inaccuracies, adjusted figure layout, and made final wording decisions after grammar and logic checking.

---

### 16. Pipeline Debugging (`debug_one_tanda.py`, `debug_plan_set.py`, `debug_select_tanda.py`)

**Prompt (reconstructed):**
> Our pipeline runs silently end-to-end through `query.py`, `fetch.py`, `ingest.py`, `select_tanda.py`, `plan_set.py`, `store.py`, and `prompt_to_features.py`. Please help write a debugging version of each script that prints and verbalizes every step in detail: what data is loaded, what the LLM returns, what gets filtered and why, how many tracks pass each stage, what scores are assigned, and which combo_key is selected. Each step should be clearly labeled and timed so we can trace failures and regressions without a debugger.

**Generated:** `debug_one_tanda.py` — full end-to-end pipeline trace for a single tanda prompt, printing step-by-step output from catalog load → Layer 1 regex → Layer 2 LLM → hard filter → soft filter → scoring → tanda grouping, with per-step elapsed time. `debug_plan_set.py` — traces the full session plan (multiple tandas + cortinas). `debug_select_tanda.py` — isolated trace for the `select_tanda` module with filter counts and score breakdowns.

**Manual edits:** Yes — added fallback display when LLM key is missing (shows "regex-only bundle"), adjusted column display widths for readability, and added the `example_steps.md` example output file showing a real run trace.

---

### 17. Evaluation Suite (`eval_00_run_all.py` through `eval_04_tanda_quality.py`)

**Prompt (reconstructed):**
> We have a set of unit tests (`test_cache_catalog.py`, `test_answer_feature.py`, `test_query_track_retrieval.py`, `test_answer_question_real.py`, `test_search_for_planning.py`, `test_answer_question_smoke.py`, `test_fetch_simple.py`, `test_cache_features_ranges.py`, `test_cache_llm_translation.py`, `test_fetch_complex.py`). Please help me combine and scale them into a sequenced evaluation suite covering four dimensions: (1) pipeline end-to-end comparison against our COT notebooks (`02a_COT_FeaturePrep.ipynb`, `02b_COT_ComboAverageBestTanda.ipynb`, `02c_COT_Analysis_ComboAverageBestTanda.ipynb`), (2) Q&A accuracy and latency, (3) caching benchmark across all cache layers, and (4) tanda quality deep-dive. The master runner `eval_00_run_all.py` should call all four and generate a report-ready Markdown summary. Also hard-code the COT notebook results (from 02a, 02b, 02c) as comparison baselines inside the eval scripts.

**Generated:** `eval_00_run_all.py` (master runner with `--quick` and `--no-llm` flags), `eval_01_pipeline_comparison.py` (vs COT baselines), `eval_02_qa_accuracy_latency.py` (pass rate, hallucination rate, latency by category), `eval_03_caching_benchmark.py` (cold/warm/speedup per cache layer), `eval_04_tanda_quality.py` (tanda structural validity, score distributions). Output JSON files + `eval_summary.md`.

**Manual edits:** Yes — actual prompts used for testing, pass/fail conditions, COT comparison values (mean latency 8.90s, out-of-bounds rate 25%) hard-coded from notebook runs, category labels for Q&A grouping, and cache speedup thresholds tuned based on observed results.

---

### 18. Image / Visualization Generation for Slides and Report

**Prompt (reconstructed):**
> Could you please help me convert these contents into a structured image/visualization: [content block]. Example: the 7-step pipeline — Natural Language Prompt → Layer 1 Regex (extracts year/decade) → Layer 2 LLM (maps prompt to orchestra, style, bpm, energy, tags) → Hard Filter (style, decade, orchestra, singer) → Soft Filter (bpm_label, energy, key, danceability) → Score & Rank (bpm, danceability, chord changes, energy, tags) → Tanda Grouping (groups by `combo_key`, selects best 3–4 tracks).

**Generated:** Slide-ready visualizations including: the 7-step tanda selection pipeline diagram, the dataset & feature engineering summary card (294 tracks, 94 Essentia features, sampling logic, tag similarity scoring), the composite score weight breakdown (BPM 0.20, danceability 0.20, energy 0.20, chords 0.15, tag sim SBERT 0.25), and the LangGraph agent routing diagram (PLAN / ADJUST / QUESTION branches). Generated as dark-background presentation slides for `DJ_Presentation.pdf`.

**Manual edits:** Yes — adjusted layout, wording, and color coding.

---

### 19. LaTeX Syntax Debugging

**Prompt (reconstructed):**
> Please explain the issue and help me debug LaTeX formatting problems. Why does indentation not work here? `\indent` did not work: `\subsection{Music Information Retrieval}\label{sec:related-mir} \indent Music Information Retrieval (MIR) provides...`

**Generated:** Explanation that `\indent` has no effect after a section heading because LaTeX's `\subsection` already starts a new paragraph context and the first paragraph of a section is intentionally not indented by default under most styles. Suggested fixes: use `\noindent` to suppress indentation consistently, or add `\usepackage{indentfirst}` to the preamble to indent all first paragraphs including post-heading ones, or restructure the paragraph so it is not the first after the heading.

**Manual edits:** Yes — tested each suggested fix in the actual `.tex` source to confirm which one matched the document's existing indentation style.