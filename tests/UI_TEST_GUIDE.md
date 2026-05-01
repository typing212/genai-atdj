# UI Manual Test Guide

**App:** AT-DJ — AI Tanda DJ
**Last updated:** 2026-04-30

Work through tests top-to-bottom; each builds on the previous. Each test has a clear input, expected result, and pass/fail verdict.

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
| 1.1 | Open the app | Empty playlist (no demo orchestras, no demo cortinas) | PASS (2026-04-28) | — |
| 1.2 | Chat panel | Single greeting from @DJ; no other messages | PASS (2026-04-28) | — |
| 1.3 | Session Log panel | Empty (no "Session started." prefilled entry) | PASS (2026-04-29) | — |
| 1.4 | Now Playing card | Dashed placeholder "No track playing — Plan a session to get started" | PASS (2026-04-28) | — |
| 1.5 | Energy Arc card | Dashed placeholder "No energy data yet — Plan a session to see the energy arc" | PASS (2026-04-28) | — |
| 1.6 | Sidebar | Settings panel only (no Sessions list); page header subtitle shows today's date | PASS (2026-04-29) | — |
| 1.7 | Quality Enhance toggle | Defaults to **OFF** | PASS (2026-04-29) | — |

---

## Test 2 — PLAN path: happy path

**Purpose:** End-to-end: with the sidebar correctly configured, a planning request actually selects tracks and the new wording shows in chat + Session Log.

**Precondition:** Sidebar configured (Provider, Model, API key, Save Settings).

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 2.1 | Type `Plan a tanda of Pugliese tangos from the 1940s`, send | Input clears immediately on send. Classifier routes to PLAN. Spinner runs ~3-10s. Chat reply: `✅ Done! I've planned 4 tracks. Orchestras: Osvaldo Pugliese. Styles: TANGO.` | PASS (2026-04-29) | 7.9s |
| 2.2 | Full Playlist | 4 tracks, all by Pugliese, decade 1940s | PASS (2026-04-29) | — |
| 2.3 | Now Playing | First Pugliese track loaded | PASS (2026-04-29) | — |
| 2.4 | Energy Arc chart | 4 dots, Y axis within 0–100% | PASS (2026-04-29) | — |
| 2.5 | Session Log shows the redesigned entries (one summary line per logical event) | `📋 PLAN — Plan started — 1 tanda(s) requested` · `📋 PLAN — Tanda 1/1 ready: 4 tracks (Osvaldo Pugliese)` · `📋 PLAN — Plan complete — 1 tanda ready` · `📋 PLAN — Log saved to session_log_<ts>.json` (and `📋 PLAN — Auto-enhanced N tracks` if Quality Enhance is ON). The detailed sub-step entries (`[cortina_selector]`, `[queue_publisher]`, etc.) live only in the JSON file now. | PASS (2026-05-01, post-redesign) | — |
| 2.6 | Check `data/log/` directory | A new `session_log_<timestamp>.json` file appears for this run; `doc/` does **not** receive any session log files | PASS (2026-04-29) | — |
| 2.7 | Send a second plan (e.g. `Plan a tanda of Di Sarli tangos from the 1940s`) | New tracks **append** to the existing playlist (don't overwrite); cortina row inserted between tandas | PASS (2026-04-30) | 6.7s |
| 2.8 | Type `Plan me a full milonga session` | Classifier routes to PLAN; multiple tandas across styles appear | PASS (2026-04-30) | 33.8s |
| 2.9 | Click **Clear** to empty the playlist, then send a new plan (e.g. `Plan a tanda of D'Arienzo tangos`) | Now Playing populates with the new first track (does **not** stay on the empty placeholder). Regression test for the cursor-stale bug fixed 2026-04-30 in `PlaybackQueue.clear()`. | PASS (2026-04-30) | 5.6s |

---

## Test 3 — PLAN path: empty result

**Purpose:** Verify graceful handling when a planning request returns 0 tracks (genuinely unmatchable, or upstream API failure): cortina insertion is skipped, the Session Log surfaces a warning with the reason, and log messages don't claim success on failure.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 3.1 | Type `Plan me a tanda of rock music from 2020`, send | Classifier routes to PLAN. Chat reply: `⚠️ Couldn't find enough tracks. Try a different prompt!` | PASS (2026-04-29) | 9.6s |
| 3.2 | Session Log per-tanda summary entry | `📋 PLAN — Tanda 1/1 skipped — no tracks` at warning level (detailed `[tanda_planner] failed in X.Xs — no candidates matched the prompt` lives only in the JSON file) | PASS (2026-05-01, post-redesign) | — |
| 3.3 | Session Log overall outcome entry | `📋 PLAN — Plan failed — no tandas could be planned` at warning level (replaces the old `0 of 1 tanda(s) succeeded` wording) | PASS (2026-05-01, post-redesign) | — |
| 3.4 | Session Log: no per-tanda success summary | Since the only attempted tanda failed, no `Tanda 1/1 ready` line is emitted | PASS (2026-05-01, post-redesign) | — |
| 3.5 | Session Log `Log saved` entry | `📋 PLAN — Log saved to session_log_<ts>.json` (info level; the JSON file still gets written even on a failed plan) | PASS (2026-05-01, post-redesign) | — |
| 3.6 | Full Playlist | Empty / unchanged — no fake cortina inserted | PASS (2026-04-29) | — |

---

## Test 4 — Q&A path

**Purpose:** Verify the RAG Q&A pipeline answers tango knowledge questions through Nancy's `fetch.py` + `query.py` (markdown → Wikipedia → LLM-only fallback).

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 4.1 | Type `Who is Carlos Di Sarli?` | Classifier routes to QUESTION. Real biographical answer mentioning pianist / orchestra leader / 1940s / smooth style | PASS (2026-04-30, after `store.py` fix) | 16.6s |
| 4.2 | Type `What is the difference between tango and vals?` | Classifier routes to QUESTION. Answer covers musical differences (rhythm, tempo, feel) | PASS (2026-04-30, after `store.py` fix) | 18.8s |
| 4.3 | Type `What BPM is Bahia Blanca?` | Classifier routes to QUESTION; returns a number or says not found | PASS (2026-04-30, after `store.py` fix) | 14.4s |
| 4.4 | Session Log after questions | No `tanda_planner` / `cortina_selector` entries — Q&A doesn't trigger the planning graph | PASS (2026-04-30) | — |

> If answers are empty: ChromaDB wasn't ingested. Run the ingest commands from Setup §2.

---

## Test 5 — Session Log captures user actions

**Purpose:** Verify the log records manual UI actions, not just agent events.

**Color key:** blue = manual action · amber = warning · green = decision/enhance · red = error

**Precondition:** A planned tanda exists in the playlist (run Test 2 first).

| # | Action | Expected log entry | Pass? | Latency |
|---|--------|-------------------|-------|---------|
| 5.1 | Click ↑ on a playlist row | `👤 You — Moved "<title>" up in playlist.` (rendered in grey) | PASS (2026-05-01, post-redesign) | 2.3s |
| 5.2 | Click ↓ on a playlist row | `👤 You — Moved "<title>" down in playlist.` (grey) | PASS (2026-05-01, post-redesign) | 2.2s |
| 5.3 | Click ✕ on a playlist row | `👤 You — Removed "<title>" from playlist.` (grey) | PASS (2026-05-01, post-redesign) | 2.2s |
| 5.4 | Click **Clear** in the playlist header | `👤 You — Cleared playlist (N tracks).` (grey) | PASS (2026-05-01, post-redesign) | 1.8s |
| 5.5 | Toggle **Quality Enhance** | `👤 You — Quality Enhance turned ON/OFF.` | PASS (2026-05-01, post-redesign) | 0.7-1.0s |
| 5.6 | Change **Transition (s)** | `👤 You — Transition gap set to Xs.` | PASS (2026-05-01, post-redesign) | 0.9s |
| 5.7 | Change **Cortina (s)** | `👤 You — Cortina length set to Xs.` | PASS (2026-05-01, post-redesign) | 0.9s |
| 5.8 | All entries have a `HH:MM:SS` timestamp | every row prefixed with `HH:MM:SS` (Tina's ISO format normalized) | PASS (2026-04-30) | — |
| 5.9 | Click ▶ on a non-current playlist row | **No log entry** — pure navigation, not a state change worth recording. Now Playing card switches to that track. | PASS (2026-05-01, post-redesign) | 2.4s |

---

## Test 6 — Energy Arc chart

**Purpose:** The chart reflects real track energy values from the catalog (not the internal planning target — that was removed).

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 6.1 | Open app before any tracks added | Dashed placeholder; no dots | PASS (2026-05-01) | — |
| 6.2 | After Test 2 plan | One dot per song; Y axis 0–100% | PASS (2026-05-01) | — |
| 6.3 | Hover over a dot | Tooltip: Song / Style / Orchestra / Singer / Decade / Source — no raw numbers | PASS (2026-05-01, structural — `#vg-tooltip-element` present) | — |
| 6.4 | Dot colors | Blue filled = played · Grey filled = upcoming planned | PASS (2026-05-01) | — |
| 6.5 | Manually add a track from library | New dot at that track's energy | PASS (2026-05-01) | 2.5s |
| 6.6 | Play a track and check chart | Dots left of current turn blue (played); dots right stay grey | PASS (2026-05-01) | 2.0s |
| 6.7 | After planning a multi-tanda session (cortinas inserted), inspect Energy Arc for the cortina rows | Cortinas appear at their playlist position as hollow squares. Their y-position is **interpolated** between the nearest songs-with-energy on either side (linear interp; flat extrapolate at the start/end). Underlying `energy` stays `None` — the interpolated y is render-only. The energy line skips cortinas (filter `type=='song'`) so the curve doesn't dip through them. | PASS (2026-05-01) — verified 16 squares show 13 distinct y-positions across an 8-tanda plan, all within the song y-range (interpolation working) | — |

> The hollow-square fallback (unknown energy) applies to anything without a numeric `energy`: (a) user-added songs whose catalog row has missing energy, (b) cortinas (which have no energy data yet). The y-position is interpolated from neighbouring anchors so the square sits on the curve. The interpolation is render-only — the underlying item still has `energy=None`.

---

## Test 7 — Playback controls

**Purpose:** Transport controls work without crashing.

**Precondition:** Playlist populated.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 7.1 | Click ▶ on a track | Track highlights; audio player loads | PASS (2026-05-01) — audio element renders inside iframe | 2.5s |
| 7.2 | ▶▶ Next | Advances to next track | PASS (2026-05-01) | 2.5s |
| 7.3 | ◀◀ Prev at first track | Stays at first; no crash, no wrap | PASS (2026-05-01) | 2.0s |
| 7.4 | ▶▶ Next at end of queue | Stops cleanly; no crash, no loop | PASS (2026-05-01) | — |
| 7.5 | Remove the currently-playing track | Player advances to next; no crash | PASS (2026-05-01) — caveat: ✕ button isn't shown on the currently-playing row, so to "remove the current track" the user must move it off-current first; verified ✕ on a non-current row does not crash | 2.0s |
| 7.6 | Set **Transition (s)** to e.g. 5; let two consecutive songs play | The audio player should insert a 5-second silent gap (or fade) between the two songs that matches the slider value | NOT TESTED — known gap (2026-05-01): need to verify that the `gap_seconds` value passed into `render_audio_player` actually changes inter-track silence; currently only verified that the input emits a log entry (Test 5.6) | — |
| 7.7 | Set **Cortina (s)** to e.g. 25; let a cortina row play | The cortina's playback duration should be capped/extended to ~25 seconds matching the slider; Now Playing card and the playlist row should also show that duration | NOT TESTED — known gap (2026-05-01): need to verify that `max_duration` passed into `render_audio_player` for cortinas actually truncates playback to the slider value | — |
| 7.8 | While a track is playing, watch the transition / progress bar inside the audio player | The progress bar should advance smoothly with playback, reach 100% at the song's duration, then trigger Next | NOT TESTED — known gap (2026-05-01): also need to confirm that the bar reflects the *processed* file's duration when Quality Enhance is ON | — |

---

## Test 8 — Auto-enhance hook on PLAN

**Purpose:** When `Quality Enhance` is **ON** at PLAN time, the audio enhancement pipeline runs automatically and the player serves the processed file.

**Precondition:** MP3 files in `data/raw/` matching the catalog.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 8.1 | Quality Enhance toggle | Defaults to **OFF** (changed 2026-04-29) | PASS (2026-04-29) | — |
| 8.2 | Turn toggle ON, plan a tanda | Log shows `Enhanced N tracks` after the planning succeeds | PASS (2026-05-01) — `Enhanced 4 tracks` log appeared after PLAN | 45s plan + ~enhance |
| 8.3 | Check `data/processed/` | New `_enhanced.wav` files appear matching the planned tracks | PASS (2026-05-01) — caveat: when re-running over previously-enhanced tracks, files are overwritten in place (mtime updated) rather than "new" appearing; the `Enhanced 4 tracks` log confirms the pipeline executed | — |
| 8.4 | Play one of those tracks | Player loads from `data/processed/`, not `data/raw/` (DevTools Network tab confirms) | NOT TESTED — requires DevTools Network inspection; out of scope for the Playwright driver | |
| 8.5 | Toggle OFF, run another plan | No `Enhanced` entry; no new files in `data/processed/` | PASS (2026-05-01) | — |
| 8.6 | Toggle ON → OFF → ON | Each state change appears as a blue log entry | PASS (2026-05-01) — 3 toggle log entries appended | 1.5s/click |

---

## Test 9 — Audio Enhancement chat path (ADJUST_AUDIO)

**Purpose:** The chat accepts natural-language audio adjustment requests, routes correctly, processes target tracks, and handles edge cases (clarification, current-song rejection, reset, persistence).

**Design intent:** The user is listening to the **currently playing** tanda. They notice it's too loud / harsh / quiet / etc. and ask the agent to apply a relative correction to the **upcoming** (next / rest) tracks. The agent measures the current track's parameters as a reference and adjusts upcoming tracks accordingly. Prompts therefore explicitly mention **current** (reference) and **next/rest** (target).

**Precondition:** A planned tanda in the playlist + MP3 files in `data/raw/`.

### 9.1 Routing

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.1.1 | Type `the current tanda is too loud, soften the next one`, send | Classifier routes to ADJUST_AUDIO (not PLAN/QUESTION); audio processing starts on the upcoming tracks (current track is the reference) | PASS (2026-05-01) — reply: `Moderately reduced loudness for 1 track` | 16.5s |

### 9.2 Standard adjustment

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.2.1 | Type `the current tanda sounds a bit too harsh, fix the next one`, send | Classifier routes to ADJUST_AUDIO. Spinner: `Analyzing and enhancing audio…` | PASS (2026-05-01) — reply: `Slightly reduced vocal presence for 1 track` | 17.0s |
| 9.2.2 | After spinner | Chat reply confirms presence reduction (mentions track count, direction) | PASS (2026-05-01) — reply mentions `1 track` + `vocal presence` | — |
| 9.2.3 | `data/processed/` | Updated `_enhanced.wav` files for those tracks (newer timestamp) | NOT TESTED — covered indirectly by 8.2/8.3; would need to capture mtime delta | — |
| 9.2.4 | Session Log | One summary entry per audio request, e.g. `🎛 AUDIO — Moderately reduced loudness for 4 tracks`. Detailed sub-step entries (`parse_request`, `measure_reference`, `compute_adjustments`, `execute_enhancement`) live only in the JSON log file. If the request can't find any target tracks, a warning summary is emitted instead: `🎛 AUDIO — No tracks to adjust — nothing matched after the current position`. | PASS (2026-05-01, post-redesign) | — |
| 9.2.5 | Play the adjusted tanda | Audibly less harsh than the original | NOT TESTED — requires human listening | — |

### 9.3 Relative constraint

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.3.1 | Plan a multi-tanda session | Multiple tracks in playlist | | |
| 9.3.2 | Type `make the rest a bit louder` | Reply states adjusted count and notes any tracks left unchanged | | |
| 9.3.3 | If some tracks were already at/above target loudness | Reply explicitly says those tracks were "left unchanged" | | — |

### 9.4 Reset / back to default

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 9.4.1 | After adjusting, type `back to default for the next tanda` | Spinner runs | PASS (2026-05-01) — reply: `Reverted 1 tracks to their default adaptive enhancement` | 9.1s |
| 9.4.2 | After spinner | Reply: tracks reverted to adaptive enhancement; no "louder/softer" wording | PASS (2026-05-01) — reply uses `default adaptive enhancement`, no `louder/softer` | — |
| 9.4.3 | Try `use original` | Same — direction=reset, re-enhanced adaptively | NOT TESTED in this Playwright run | — |
| 9.4.4 | Try `undo my changes` | Same | NOT TESTED in this Playwright run | — |

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
| 10.1 | Cold start (`uv run streamlit run main.py`), open browser | Page renders without any error / traceback panel | PASS (2026-04-29) | — |
| 10.2 | Edit `atdj/ui/page_main.py` (e.g., add a comment), save | Streamlit auto-reloads cleanly; no duplicate-key error appears | PASS (2026-04-29) | — |
| 10.3 | Send a chat message and trigger a rerun mid-edit | No duplicate-key error after the rerun | PASS (2026-04-29) | — |

> Background: previously `app.py` had a module-level `run_app()` call AND `main.py` called `run_app()` — so the page rendered twice per script run, causing intermittent duplicate-key errors on every widget (`sb_provider`, `sb_model`, etc.). The module-level call was removed.

---

## Test 11 — Sidebar settings

**Purpose:** Provider/model/key changes propagate without a restart.

**Note (2026-05-01):** the row numbering in this section was historically `10.1–10.5` (a typo carried over from Test 10). Re-verified rows below use the section's correct `11.x` numbering.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 11.1 | Open sidebar | Settings panel visible (no Sessions list above it) | PASS (2026-05-01) | — |
| 11.2 | Change Provider to Gemini | Model dropdown updates to Gemini models | FAIL (2026-05-01) — after switching to **Gemini**, the model dropdown text reads `Others` instead of a Gemini model name (e.g., `gemini-1.5-pro`). Suspected root cause: provider→model coupling not refreshing the model dropdown options/value when provider changes; the dropdown may be falling back to a generic "Others" placeholder. Needs investigation in `_sidebar()` of `atdj/ui/page_main.py`. | 1–2s |
| 11.3 | Paste a key, click Save Settings | Toast "Settings saved.", no crash | PASS (2026-05-01) — toast text confirmed, no crash | 1.5s |
| 11.4 | Send a chat request | Uses the newly selected provider (visible in any failure message via the diagnostic suffix) | NOT TESTED — would need a Gemini API key in the sidebar to actually exercise the Gemini path; the structural switch is partly covered by 11.2 (which is failing) | |
| 11.5 | Switch back to Claude | Claude models shown; prior chat history unaffected | FAIL (2026-05-01) — same root cause as 11.2: after switching back to **Claude**, the model dropdown text still reads `Others` instead of a Claude model. Chat history (25 messages) is preserved correctly. | 1–2s |

---

## Test 12 — Search Music (manual library)

**Purpose:** The Search Music section lets the user find and add tracks (and ideally cortinas) to the playlist by hand.

| # | Action | Expected | Pass? | Latency |
|---|--------|----------|-------|---------|
| 12.1 | Type a song title or orchestra in search → click ＋ on a result | Track appended to end of playlist; Energy Arc gets a new mark | PASS (2026-05-01) — covered indirectly by Test 6.5 | 2.5s |
| 12.2 | Type a cortina-style query (e.g. `cortina`, or a known cortina filename like `sucker`) and click `＋` on a result to add it to the playlist | Cortina results render with a `C` badge (filename + " · cortina"); `＋` appends a `{"type": "cortina"}` entry to the end of the playlist; chart gains a hollow square at the cortina's playlist position; user log line: `👤 You — Added cortina "<filename>" to playlist end.` | PASS (2026-05-01) — verified `cortina` returns 6 matches; `sucker` returns 1 match; click `＋` adds the cortina (chart hollow squares went 3 → 4) | 2.0s |

---

## Pass/Fail summary

| Test | Description | Status |
|------|-------------|--------|
| 1 | Fresh start state | PASS (2026-04-29) |
| 2 | PLAN path — happy path | PASS (2026-04-29) |
| 3 | PLAN path — empty result | PASS (2026-04-29) |
| 4 | Q&A path | PASS (2026-04-30) |
| 5 | Session Log — user actions | PASS (2026-04-30) |
| 6 | Energy Arc chart | PASS (2026-05-01) — 6.7 cortina hollow-square fallback now wired up |
| 7 | Playback controls | partial PASS (2026-05-01) — 7.1–7.5 PASS; 7.6 (Transition gap), 7.7 (Cortina length), 7.8 (progress bar) NOT TESTED |
| 8 | Auto-enhance hook on PLAN | PASS (2026-05-01) — 8.4 not tested (DevTools needed) |
| 9 | Audio Enhancement chat path | partial PASS (2026-05-01) — 9.1.1, 9.2.1, 9.2.2, 9.4.1, 9.4.2 PASS; 9.3, 9.5, 9.6, 9.7 NOT TESTED |
| 10 | App boots without duplicate-key errors | PASS (2026-04-29) |
| 11 | Sidebar settings | partial — 11.1, 11.3 PASS; 11.2, 11.5 FAIL (model dropdown shows "Others" after provider switch); 11.4 not tested |
| 12 | Search Music (library) | PASS (2026-05-01) — 12.1 PASS (via 6.5); 12.2 PASS — cortinas now searchable + addable |

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
