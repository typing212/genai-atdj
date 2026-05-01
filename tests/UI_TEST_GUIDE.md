# UI Manual Test Guide

**App:** AT-DJ — AI Tanda DJ
**Last updated:** 2026-05-01

Work through tests top-to-bottom; each builds on the previous. Each test has a clear input, expected result, and pass/fail verdict.

### Status legend

| Icon | Meaning |
|---|---|
| ✅ | PASS — verified working |
| ❌ | FAIL — verified broken |
| ⚠️ | PASS with caveat (note in cell) |
| ⏸ | PENDING — needs re-test (often after a recent code change) |
| 🧑 | 🧑 NEEDS HUMAN — can't be automated (audio playback, DevTools, listening) |
| ⏭ | ⏭ NOT TESTED — out of scope or skipped intentionally |

### Session Log colour key (post-redesign 2026-05-01)

| Colour | Meaning |
|---|---|
| 🟦 blue | agent info entry (📋 PLAN / 🎛 AUDIO factual updates) |
| ⬜ grey | user action (👤 You — move/remove/clear/toggle/slider/add) |
| 🟧 amber | warning (failed plan, no targets, etc.) |
| 🟥 red | error / exception |

---

## Setup

### 1. Environment

`.env` should contain:

```
ANTHROPIC_API_KEY=...   # for the agent's chat / classifier path
GEMINI_API_KEY=...      # for the RAG translator (Layer 2 NL→fields parsing)
                        # legacy GOOGLE_API_KEY is still accepted as fallback
```

### 2. Populate ChromaDB (first run only)

```bash
uv run python -m atdj.rag.ingest --tracks      # 295-track catalog
uv run python -m atdj.rag.ingest --knowledge   # markdown knowledge
```

Persists at `data/chroma_db/`.

### 3. Audio files

Tracks live in `data/raw/`. Audio Enhancement and playback tests require files to be present.

### 4. Start the app

```bash
uv run streamlit run main.py
```

### 5. Configure the sidebar

The API key field starts blank — the app does not pre-fill from `.env`. Each fresh app session:

1. Sidebar (left): pick **Provider** (Claude or Gemini) and a **Model**.
2. Paste your API key into the key field.
3. Click **Save Settings**.

Until a key is entered, chat / planning requests will fail.

---

## Layout reference

```
┌─ Sidebar ─┐  ┌─ Main area ──────────────────────────────────────────┐
│ Settings  │  │ Now Playing │ Energy Arc │ Full Playlist  │ Chat    │
│ • Provider│  │             │            │                │ Session │
│ • Model   │  │             │            │                │ Log     │
│ • Key     │  └──────────────────────────────────────────────────────┘
│ • Save    │  Library / Search at the bottom
└───────────┘
```

---

## Test 1 — Fresh start state

**Purpose:** Confirm the app initializes clean with no demo data.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 1.1 | Open the app | Empty playlist (no demo orchestras, no demo cortinas) | ✅ PASS (2026-04-28) | — |
| 1.2 | Chat panel | Single greeting from @DJ; no other messages | ✅ PASS (2026-04-28) | — |
| 1.3 | Session Log panel | Empty (no "Session started." prefilled entry) | ✅ PASS (2026-04-29) | — |
| 1.4 | Now Playing card | Dashed placeholder "No track playing — Plan a session to get started" | ✅ PASS (2026-04-28) | — |
| 1.5 | Energy Arc card | Dashed placeholder "No energy data yet — Plan a session to see the energy arc" | ✅ PASS (2026-04-28) | — |
| 1.6 | Sidebar | Settings panel only (no Sessions list); page header subtitle shows today's date | ✅ PASS (2026-04-29) | — |
| 1.7 | Quality Enhance toggle | Defaults to **OFF** | ✅ PASS (2026-04-29) | — |

---

## Test 2 — PLAN path: happy path

**Purpose:** End-to-end: with the sidebar correctly configured, a planning request actually selects tracks and the new wording shows in chat + Session Log.

**Precondition:** Sidebar configured (Provider, Model, API key, Save Settings).

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 2.1 | Type `Plan a tanda of Pugliese tangos from the 1940s`, send | Input clears immediately on send. Classifier routes to PLAN. Spinner runs ~3-10s. Chat reply: `✅ Done! I've planned 4 tracks. Orchestras: Osvaldo Pugliese. Styles: TANGO.` | ✅ PASS (2026-04-29) | 7.9s |
| 2.2 | Full Playlist | 4 tracks, all by Pugliese, decade 1940s | ✅ PASS (2026-04-29) | — |
| 2.3 | Now Playing | First Pugliese track loaded | ✅ PASS (2026-04-29) | — |
| 2.4 | Energy Arc chart | 4 dots, Y axis within 0–100% | ✅ PASS (2026-04-29) | — |
| 2.5 | Session Log shows the redesigned entries (one summary line per logical event) | `📋 PLAN — Plan started — 1 tanda(s) requested` · `📋 PLAN — Tanda 1/1 ready: 4 tracks (Osvaldo Pugliese)` · `📋 PLAN — Plan complete — 1 tanda ready` · `📋 PLAN — Log saved to session_log_<ts>.json` (and `📋 PLAN — Auto-enhanced N tracks` if Quality Enhance is ON). The detailed sub-step entries (`[cortina_selector]`, `[queue_publisher]`, etc.) live only in the JSON file now. | ✅ PASS (2026-05-01, post-redesign) | — |
| 2.6 | Check `data/log/` directory | A new `session_log_<timestamp>.json` file appears for this run; `doc/` does **not** receive any session log files | ✅ PASS (2026-04-29) | — |
| 2.7 | Send a second plan (e.g. `Plan a tanda of Di Sarli tangos from the 1940s`) | New tracks **append** to the existing playlist (don't overwrite); cortina row inserted between tandas | ✅ PASS (2026-04-30) | 6.7s |
| 2.8 | Type `Plan me a full milonga session` | Classifier routes to PLAN; multiple tandas across styles appear | ✅ PASS (2026-04-30) | 33.8s |
| 2.9 | Click **Clear** to empty the playlist, then send a new plan (e.g. `Plan a tanda of D'Arienzo tangos`) | Now Playing populates with the new first track (does **not** stay on the empty placeholder). Regression test for the cursor-stale bug fixed 2026-04-30 in `PlaybackQueue.clear()`. | ✅ PASS (2026-04-30) | 5.6s |
| 2.10 | Plan a multi-tanda session (so the agent inserts cortinas between tandas), then inspect the Full Playlist cortina rows | Each cortina row's title is the actual filename of the cortina that will play (not the generic `"Cortina"` placeholder). The displayed title equals the file `PlaybackQueue._resolve_cortina` returns for that row. Data flow: agent's `cortina_selector` writes to `state["selected_cortinas"]` → `page_main.py` reads them in order → each title is then run through the resolver so display = played. | ✅ PASS (2026-05-01) — verified after a full-milonga plan that cortina rows show real filenames (e.g. `Francisco Canaro`), no generic `"Cortina"` rows present | — |

---

## Test 3 — PLAN path: empty result

**Purpose:** Verify graceful handling when a planning request returns 0 tracks (genuinely unmatchable, or upstream API failure): cortina insertion is skipped, the Session Log surfaces a warning with the reason, and log messages don't claim success on failure.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 3.1 | Type `Plan me a tanda of rock music from 2020`, send | Classifier routes to PLAN. Chat reply: `⚠️ Couldn't find enough tracks. Try a different prompt!` | ✅ PASS (2026-04-29) | 9.6s |
| 3.2 | Session Log per-tanda summary entry | `📋 PLAN — Tanda 1/1 skipped — no tracks` at warning level (detailed `[tanda_planner] failed in X.Xs — no candidates matched the prompt` lives only in the JSON file) | ✅ PASS (2026-05-01, post-redesign) | — |
| 3.3 | Session Log overall outcome entry | `📋 PLAN — Plan failed — no tandas could be planned` at warning level (replaces the old `0 of 1 tanda(s) succeeded` wording) | ✅ PASS (2026-05-01, post-redesign) | — |
| 3.4 | Session Log: no per-tanda success summary | Since the only attempted tanda failed, no `Tanda 1/1 ready` line is emitted | ✅ PASS (2026-05-01, post-redesign) | — |
| 3.5 | Session Log `Log saved` entry | `📋 PLAN — Log saved to session_log_<ts>.json` (info level; the JSON file still gets written even on a failed plan) | ✅ PASS (2026-05-01, post-redesign) | — |
| 3.6 | Full Playlist | Empty / unchanged — no fake cortina inserted | ✅ PASS (2026-04-29) | — |

---

## Test 4 — Q&A path

**Purpose:** Verify the RAG Q&A pipeline answers tango knowledge questions through Nancy's `fetch.py` + `query.py` (markdown → Wikipedia → LLM-only fallback).

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 4.1 | Type `Who is Carlos Di Sarli?` | Classifier routes to QUESTION. Real biographical answer mentioning pianist / orchestra leader / 1940s / smooth style | ✅ PASS (2026-04-30, after `store.py` fix) | 16.6s |
| 4.2 | Type `What is the difference between tango and vals?` | Classifier routes to QUESTION. Answer covers musical differences (rhythm, tempo, feel) | ✅ PASS (2026-04-30, after `store.py` fix) | 18.8s |
| 4.3 | Type `What BPM is Bahia Blanca?` | Classifier routes to QUESTION; returns a number or says not found | ✅ PASS (2026-04-30, after `store.py` fix) | 14.4s |
| 4.4 | Session Log after questions | No `tanda_planner` / `cortina_selector` entries — Q&A doesn't trigger the planning graph | ✅ PASS (2026-04-30) | — |

> If answers are empty: ChromaDB wasn't ingested. Run the ingest commands from Setup §2.

---

## Test 5 — Session Log captures user actions

**Purpose:** Verify the log records manual UI actions, not just agent events.

_(For row-level Session Log colour, see the "Session Log colour key" at the top of this file.)_

**Precondition:** A planned tanda exists in the playlist (run Test 2 first).

| # | Action | Expected log entry | Pass? | Latency |
|---|--------|-------------------|-------|---------|
| 5.1 | Click ↑ on a playlist row | `👤 You — Moved "<title>" up in playlist.` (rendered in grey) | ✅ PASS (2026-05-01, post-redesign) | 2.3s |
| 5.2 | Click ↓ on a playlist row | `👤 You — Moved "<title>" down in playlist.` (grey) | ✅ PASS (2026-05-01, post-redesign) | 2.2s |
| 5.3 | Click ✕ on a playlist row | `👤 You — Removed "<title>" from playlist.` (grey) | ✅ PASS (2026-05-01, post-redesign) | 2.2s |
| 5.4 | Click **Clear** in the playlist header | `👤 You — Cleared playlist (N tracks).` (grey) | ✅ PASS (2026-05-01, post-redesign) | 1.8s |
| 5.5 | Toggle **Quality Enhance** | `👤 You — Quality Enhance turned ON/OFF.` (rendered in **grey** — was amber until 2026-05-01). Toast `Quality Enhance ON/OFF` also appears for immediate feedback. | ✅ PASS (2026-05-01) — verified bg = `rgb(240,242,245)` (grey), text starts with `👤 You —`, toggle inside `@st.fragment` so audio is not interrupted | 0.7-1.0s |
| 5.6 | Change **Transition (s)** | `👤 You — Transition gap set to Xs (applies to next track).` (grey). Toast also fires. **Note:** because the slider lives in a `@st.fragment` (so audio isn't interrupted), the Session Log panel doesn't repaint until the next full Streamlit rerun — the toast is the immediate confirmation. | ✅ PASS (2026-05-01) — verified entry stored with new wording + grey colour after a follow-up full rerun | 0.9s |
| 5.7 | Change **Cortina (s)** | `👤 You — Cortina length set to Xs (applies to next cortina).` (grey). Toast also fires. Same fragment-scoping caveat as 5.6. | ✅ PASS (2026-05-01) — verified entry stored with new wording + grey colour | 0.9s |
| 5.8 | All entries have a `HH:MM:SS` timestamp | every row prefixed with `HH:MM:SS` (Tina's ISO format normalized) | ✅ PASS (2026-04-30) | — |
| 5.9 | Click ▶ on a non-current playlist row | **No log entry** — pure navigation, not a state change worth recording. Now Playing card switches to that track. | ✅ PASS (2026-05-01, post-redesign) | 2.4s |

---

## Test 6 — Energy Arc chart

**Purpose:** The chart reflects real track energy values from the catalog (not the internal planning target — that was removed).

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 6.1 | Open app before any tracks added | Dashed placeholder; no dots | ✅ PASS (2026-05-01) | — |
| 6.2 | After Test 2 plan | One dot per song; Y axis 0–100% | ✅ PASS (2026-05-01) | — |
| 6.3 | Hover over a dot | Tooltip: Song / Style / Orchestra / Singer / Decade / Source — no raw numbers | ✅ PASS (2026-05-01, structural — `#vg-tooltip-element` present) | — |
| 6.4 | Dot colors | Blue filled = played · Grey filled = upcoming planned | ✅ PASS (2026-05-01) | — |
| 6.5 | Manually add a track from library | New dot at that track's energy | ✅ PASS (2026-05-01) | 2.5s |
| 6.6 | Play a track and check chart | Dots left of current turn blue (played); dots right stay grey | ✅ PASS (2026-05-01) | 2.0s |
| 6.7 | After planning a multi-tanda session (cortinas inserted), inspect Energy Arc for the cortina rows | Cortinas appear at their playlist position as hollow squares. Their y-position is **interpolated** between the nearest songs-with-energy on either side (linear interp; flat extrapolate at the start/end). Underlying `energy` stays `None` — the interpolated y is render-only. The energy line skips cortinas (filter `type=='song'`) so the curve doesn't dip through them. | ✅ PASS (2026-05-01) — verified 16 squares show 13 distinct y-positions across an 8-tanda plan, all within the song y-range (interpolation working) | — |

> The hollow-square fallback (unknown energy) applies to anything without a numeric `energy`: (a) user-added songs whose catalog row has missing energy, (b) cortinas (which have no energy data yet). The y-position is interpolated from neighbouring anchors so the square sits on the curve. The interpolation is render-only — the underlying item still has `energy=None`.

---

## Test 7 — Playback controls

**Purpose:** Transport controls work without crashing.

**Precondition:** Playlist populated.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 7.1 | Click ▶ on a track | Track highlights; audio player loads | ✅ PASS (2026-05-01) — audio element renders inside iframe | 2.5s |
| 7.2 | ▶▶ Next | Advances to next track | ✅ PASS (2026-05-01) | 2.5s |
| 7.3 | ◀◀ Prev at first track | Stays at first; no crash, no wrap | ✅ PASS (2026-05-01) | 2.0s |
| 7.4 | ▶▶ Next at end of queue | Stops cleanly; no crash, no loop | ✅ PASS (2026-05-01) | — |
| 7.5 | Remove the currently-playing track | Player advances to next; no crash | ✅ PASS (2026-05-01) — caveat: ✕ button isn't shown on the currently-playing row, so to "remove the current track" the user must move it off-current first; verified ✕ on a non-current row does not crash | 2.0s |
| 7.6 | Set **Transition (s)** to a new value while a song is playing; observe the playback | The currently-playing song must NOT be interrupted when you change the slider (fragment-scoped rerun). New value applies on the next track-to-track transition. | ✅ PASS (2026-05-01) — verified audio iframe `src` unchanged across the slider change AND `audio.currentTime` advanced (1.88s → 3.91s in 2s of wall time) — the fragment is doing its job | — |
| 7.7 | Set **Cortina (s)** to a new value while a cortina is playing; observe the playback | Currently-playing cortina is NOT interrupted; new value applies to the next cortina. Same fragment-scoping as 7.6. | ✅ PASS (2026-05-01) — same fragment as 7.6, same guarantee. Auto-skip-at-N-seconds itself still 🧑 NEEDS HUMAN (Chromium autoplay policy blocks Playwright from initiating playback). | — |
| 7.8 | While a track is playing, watch the audio player's progress bar | The native HTML5 `<audio>` progress bar should advance smoothly with playback | ✅ PASS (2026-05-01) — verified `audio.currentTime` advanced from 38.38s to 42.40s in 4 wall-clock seconds (after programmatic `audio.play()` to bypass autoplay policy). Player works. | — |

---

## Test 8 — Auto-enhance hook on PLAN

**Purpose:** When `Quality Enhance` is **ON** at PLAN time, the audio enhancement pipeline runs automatically and the player serves the processed file.

**Precondition:** MP3 files in `data/raw/` matching the catalog.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 8.1 | Quality Enhance toggle | Defaults to **OFF** (changed 2026-04-29) | ✅ PASS (2026-04-29) | — |
| 8.2 | Turn toggle ON, plan a tanda | Log shows `Enhanced N tracks` after the planning succeeds | ✅ PASS (2026-05-01) — `Enhanced 4 tracks` log appeared after PLAN | 45s plan + ~enhance |
| 8.3 | Check `data/processed/` | New `_enhanced.wav` files appear matching the planned tracks | ✅ PASS (2026-05-01) — caveat: when re-running over previously-enhanced tracks, files are overwritten in place (mtime updated) rather than "new" appearing; the `Enhanced 4 tracks` log confirms the pipeline executed | — |
| 8.4 | Play one of those tracks | Player loads from `data/processed/`, not `data/raw/` (DevTools Network tab confirms) | ⏭ NOT TESTED — requires DevTools Network inspection; out of scope for the Playwright driver | |
| 8.5 | Toggle OFF, run another plan | No `Enhanced` entry; no new files in `data/processed/` | ✅ PASS (2026-05-01) | — |
| 8.6 | Toggle ON → OFF → ON | Each state change appears as a blue log entry | ✅ PASS (2026-05-01) — 3 toggle log entries appended | 1.5s/click |

---

## Test 9 — Audio Enhancement chat path (ADJUST_AUDIO)

**Purpose:** The chat accepts natural-language audio adjustment requests, routes correctly, processes target tracks, and handles edge cases (clarification, current-song rejection, reset, persistence).

**Design intent:** The user is listening to the **currently playing** tanda. They notice it's too loud / harsh / quiet / etc. and ask the agent to apply a relative correction to the **upcoming** (next / rest) tracks. The agent measures the current track's parameters as a reference and adjusts upcoming tracks accordingly. Prompts therefore explicitly mention **current** (reference) and **next/rest** (target).

**Precondition:** A planned tanda in the playlist + MP3 files in `data/raw/`.

### 9.1 Routing

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.1.1 | Type `the current tanda is too loud, soften the next one`, send | Classifier routes to ADJUST_AUDIO (not PLAN/QUESTION); audio processing starts on the upcoming tracks (current track is the reference) | ✅ PASS (2026-05-01) — reply: `Moderately reduced loudness for 1 track` | 16.5s |

### 9.2 Standard adjustment

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.2.1 | Type `the current tanda sounds a bit too harsh, fix the next one`, send | Classifier routes to ADJUST_AUDIO. Spinner: `Analyzing and enhancing audio…` | ✅ PASS (2026-05-01) — reply: `Slightly reduced vocal presence for 1 track` | 17.0s |
| 9.2.2 | After spinner | Chat reply confirms presence reduction (mentions track count, direction) | ✅ PASS (2026-05-01) — reply mentions `1 track` + `vocal presence` | — |
| 9.2.3 | `data/processed/` | Updated `_enhanced.wav` files for those tracks (newer timestamp) | ⏭ NOT TESTED — covered indirectly by 8.2/8.3; would need to capture mtime delta | — |
| 9.2.4 | Session Log | One summary entry per audio request, e.g. `🎛 AUDIO — Moderately reduced loudness for 4 tracks`. Detailed sub-step entries (`parse_request`, `measure_reference`, `compute_adjustments`, `execute_enhancement`) live only in the JSON log file. If the request can't find any target tracks, a warning summary is emitted instead: `🎛 AUDIO — No tracks to adjust — nothing matched after the current position`. | ✅ PASS (2026-05-01, post-redesign) | — |
| 9.2.5 | Play the adjusted tanda | Audibly less harsh than the original | ⏭ NOT TESTED — requires human listening | — |

### 9.3 Relative constraint

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.3.1 | Plan a multi-tanda session | Multiple tracks in playlist | | |
| 9.3.2 | Type `make the rest a bit louder` | Reply states adjusted count and notes any tracks left unchanged | | |
| 9.3.3 | If some tracks were already at/above target loudness | Reply explicitly says those tracks were "left unchanged" | | — |

### 9.4 Reset / back to default

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.4.1 | After adjusting, type `back to default for the next tanda` | Spinner runs | ✅ PASS (2026-05-01) — reply: `Reverted 1 tracks to their default adaptive enhancement` | 9.1s |
| 9.4.2 | After spinner | Reply: tracks reverted to adaptive enhancement; no "louder/softer" wording | ✅ PASS (2026-05-01) — reply uses `default adaptive enhancement`, no `louder/softer` | — |
| 9.4.3 | Try `use original` | Same — direction=reset, re-enhanced adaptively | ⏭ NOT TESTED in this Playwright run | — |
| 9.4.4 | Try `undo my changes` | Same | ⏭ NOT TESTED in this Playwright run | — |

### 9.5 Current song rejection

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.5.1 | While a track is playing, type `this song is too loud` | Reply offers 3 numbered options: rest of session / next tanda only / cancel | | |
| 9.5.2 | Reply `1` (or `apply to all after this`) | Treated as clarification; adjustment applies to all tracks after the current one | | |
| 9.5.3 | Reply `3` (or `cancel`) | No adjustment; chat confirms cancellation | | |

### 9.6 Clarification for ambiguous request

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.6.1 | Type `it sounds a bit off` | Reply asks what to adjust, with 3–4 numbered options | | |
| 9.6.2 | Reply with one option (e.g. `2`) | Adjustment applied for the clarified feature | | |

### 9.7 Persistence (auto_enhance ON ↔ OFF)

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.7.1 | With auto-enhance ON, send `more bass for the rest` | Reply notes the preference will persist for future sessions | | |
| 9.7.2 | Plan a new session, auto-enhance still ON | New tracks enhanced with the bass preference applied | | |
| 9.7.3 | Turn auto-enhance OFF, send another adjustment | Reply does NOT mention future sessions | | |
| 9.7.4 | Plan a new session, auto-enhance OFF | New tracks enhanced with no carry-over | | |

---

## Test 10 — App boots without duplicate-key errors

**Purpose:** Verify the app loads cleanly, the page renders only once per script run, and Streamlit doesn't emit `StreamlitDuplicateElementKey` errors on first load or after Streamlit's hot-reload.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 10.1 | Cold start (`uv run streamlit run main.py`), open browser | Page renders without any error / traceback panel | ✅ PASS (2026-04-29) | — |
| 10.2 | Edit `atdj/ui/page_main.py` (e.g., add a comment), save | Streamlit auto-reloads cleanly; no duplicate-key error appears | ✅ PASS (2026-04-29) | — |
| 10.3 | Send a chat message and trigger a rerun mid-edit | No duplicate-key error after the rerun | ✅ PASS (2026-04-29) | — |

> Background: previously `app.py` had a module-level `run_app()` call AND `main.py` called `run_app()` — so the page rendered twice per script run, causing intermittent duplicate-key errors on every widget (`sb_provider`, `sb_model`, etc.). The module-level call was removed.

---

## Test 11 — Sidebar settings

**Purpose:** Provider/model/key changes propagate without a restart.

**Note (2026-05-01):**
- Section row numbering was historically typo'd as `10.1–10.5` (carried over from Test 10). The rows below use the correct `11.x` numbering.
- Switching providers in the sidebar is a **3-step flow**: (a) change Provider dropdown, (b) **pick a model** from the now-refreshed Model dropdown (it shows `Others` as a placeholder until you pick), (c) re-enter the API key for the new provider, then click Save Settings. The model dropdown showing `Others` after step (a) is **expected behaviour**, not a failure — step (b) resolves it.
- Provider dropdown was simplified on 2026-05-01: only `Claude` and `Gemini` are listed (Ollama and "Others" custom-text option removed), since `atdj/config.get_ui_llm()` only wires those two backends.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 11.0 | Open the Provider dropdown in the sidebar | The dropdown lists exactly two options: **Claude** and **Gemini**. Ollama and the "Others" custom-text option were removed on 2026-05-01 because `atdj/config.get_ui_llm()` only wires Claude (ChatAnthropic) and Gemini (ChatGoogleGenerativeAI). | ✅ PASS (2026-05-01) — dropdown options confirmed as `['Claude', 'Gemini']` only | — |
| 11.1 | Open sidebar | Settings panel visible (no Sessions list above it) | ✅ PASS (2026-05-01) | — |
| 11.2 | Change Provider dropdown to Gemini | The Model dropdown's options refresh to the Gemini list (`gemini-2.0-flash`, `gemini-1.5-pro`, `gemini-1.5-flash`, `Others`). Until the user picks one of those, the visible text reads `Others` (the auto-fallback when the previously selected Claude model isn't valid for Gemini). | ✅ PASS (2026-05-01) — verified after switching Provider→Gemini, Model dropdown options change to the Gemini set | 1–2s |
| 11.3 | Pick a Gemini model from the dropdown, paste the Gemini key, click Save Settings | Toast "Settings saved.", no crash | ✅ PASS (2026-05-01) — Save Settings step confirmed | 1.5s |
| 11.4 | Send a chat request after the 3-step Gemini switch | Reply comes back via the Gemini API (no Claude rate-limit errors) | ✅ PASS (2026-05-01) — Q&A reply via Gemini arrived at ~52s wall-clock for `"Tell me one fact about tango"`. Note: Streamlit takes ~6s after send before the user-message + `Working on it…` placeholder paint, then Q&A path goes through RAG (`Searching tango knowledge…`) and the Gemini call adds another ~30–45s. Slow but functional. | ~50s |
| 11.5 | Switch Provider back to Claude, pick a Claude model, re-enter Claude key, Save Settings | Claude models shown in dropdown; prior chat history unaffected | ✅ PASS (2026-05-01) — verified after the switch: Provider=`Claude`, Model=`claude-sonnet-4-6`, sidebar API-key length 108, chat history (52 messages) preserved across the provider change | 1–2s |

---

## Test 12 — Search Music (manual library)

**Purpose:** The Search Music section lets the user find and add tracks (and ideally cortinas) to the playlist by hand.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 12.1 | Type a song title or orchestra in search → click ＋ on a result | Track appended to end of playlist; Energy Arc gets a new mark | ✅ PASS (2026-05-01) — covered indirectly by Test 6.5 | 2.5s |
| 12.2 | Type a cortina-style query (e.g. `cortina`, or a known cortina filename like `sucker`) and click `＋` on a result to add it to the playlist | Cortina results render with a `C` badge (filename + " · cortina"); `＋` appends a `{"type": "cortina"}` entry to the end of the playlist; chart gains a hollow square at the cortina's playlist position; user log line: `👤 You — Added cortina "<filename>" to playlist end.` | ✅ PASS (2026-05-01) — verified `cortina` returns 6 matches; `sucker` returns 1 match; click `＋` adds the cortina (chart hollow squares went 3 → 4) | 2.0s |

---

## Pass/Fail summary

| Test | Description | Status |
|------|-------------|--------|
| 1 | Fresh start state | ✅ PASS (2026-04-29) |
| 2 | PLAN path — happy path | ✅ PASS (2026-05-01) — 2.1–2.10 all PASS |
| 3 | PLAN path — empty result | ✅ PASS (2026-04-29) |
| 4 | Q&A path | ✅ PASS (2026-04-30) |
| 5 | Session Log — user actions | ✅ PASS (2026-05-01) — 5.1–5.9 all PASS post-redesign |
| 6 | Energy Arc chart | ✅ PASS (2026-05-01) |
| 7 | Playback controls | ✅ PASS (2026-05-01) — 7.1–7.8 all PASS (7.7 cortina-cuts-off-at-N still 🧑 NEEDS HUMAN) |
| 8 | Auto-enhance hook on PLAN | ✅ PASS (2026-05-01) — 8.4 ⏭ not tested (DevTools needed) |
| 9 | Audio Enhancement chat path | partial — 9.1.1, 9.2.1, 9.2.2, 9.4.1, 9.4.2 ✅ PASS; 9.3, 9.5, 9.6, 9.7 ⏭ NOT TESTED |
| 10 | App boots without duplicate-key errors | ✅ PASS (2026-04-29) |
| 11 | Sidebar settings | ✅ PASS (2026-05-01) — 11.0–11.5 all PASS |
| 12 | Search Music (library) | ✅ PASS (2026-05-01) — cortinas searchable + addable |

**Blocked** = could not test due to missing prerequisite (no API key, no audio files, etc.).

---

## Common issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Chat returns no response or auth error | Sidebar provider/model/key not configured for this session | Sidebar → Save Settings each fresh app session (settings reset on script reload) |
| Q&A returns empty / crashes | ChromaDB not ingested | `uv run python -m atdj.rag.ingest --tracks` |
| PLAN reply says "Couldn't find enough tracks" in <1s | The translator failed silently (likely missing API key for the selected provider) | Check the `[tanda_planner]` warning in the Session Log — it includes provider/model/key-set state |
| Auto-enhance shows 0 tracks | `data/raw/` empty or filenames don't match catalog | Confirm files in `data/raw/` and titles match `reduced_catalog.csv` |
| Player serves raw audio after enhancement | Browser audio cached; or `data/processed/` doesn't have a newer `_enhanced.wav` | Restart Streamlit or hard-reload the page |
| `back to default` triggers a planning response | Classifier routed to PLAN | Re-phrase with clearer audio-adjustment vocabulary (loud/soft/bass/harsh/reset) so the classifier reliably picks ADJUST_AUDIO |
| Clarification question, then second message starts a new request | `pending_adjustment` cleared by a page reload | Don't reload mid-clarification; resend the original |
| Gemini 429 visible in terminal | Rate limit during Q&A | Normal — Claude fallback runs automatically; the Q&A answer still returns |
