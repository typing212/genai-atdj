# UI Manual Test Guide

**App:** AT-DJ — AI Tanda DJ
**Last updated:** 2026-04-29

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

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 1.1 | Open the app | Empty playlist (no demo orchestras, no demo cortinas) | PASS (2026-04-28) |
| 1.2 | Chat panel | Single greeting from @DJ; no other messages | PASS (2026-04-28) |
| 1.3 | Session Log panel | Empty (no "Session started." prefilled entry) | PASS (2026-04-29) |
| 1.4 | Now Playing card | Dashed placeholder "No track playing — Plan a session to get started" | PASS (2026-04-28) |
| 1.5 | Energy Arc card | Dashed placeholder "No energy data yet — Plan a session to see the energy arc" | PASS (2026-04-28) |
| 1.6 | Sidebar | Settings panel only (no Sessions list); page header subtitle shows today's date | PASS (2026-04-29) |
| 1.7 | Quality Enhance toggle | Defaults to **OFF** | PASS (2026-04-29) |

---

## Test 2 — PLAN path: happy path

**Purpose:** End-to-end: with the sidebar correctly configured, a planning request actually selects tracks and the new wording shows in chat + Session Log.

**Precondition:** Sidebar configured (Provider, Model, API key, Save Settings).

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 2.1 | Set chat context to **Tanda Planning**, type `Plan a tanda of Pugliese tangos from the 1940s`, send | Input clears immediately on send. Spinner runs ~3-10s. Chat reply: `✅ Done! I've planned 4 tracks. Orchestras: Osvaldo Pugliese. Styles: TANGO.` | PASS (2026-04-29) |
| 2.2 | Full Playlist | 4 tracks, all by Pugliese, decade 1940s | PASS (2026-04-29) |
| 2.3 | Now Playing | First Pugliese track loaded | PASS (2026-04-29) |
| 2.4 | Energy Arc chart | 4 dots, Y axis within 0–100% | PASS (2026-04-29) |
| 2.5 | Session Log shows these entries (info level except where noted) | `[session_init] Plan started — 1 tanda(s) requested` · `[tanda_planner] Tanda 1/1 planned in X.Xs (4 tracks)` · `[cortina_selector] Cortina selected: ...` · `[queue_publisher] Tanda 1 published to queue.` · `[session_summary] Plan complete: 1 tanda(s).` | PASS (2026-04-29) |
| 2.6 | Check `data/log/` directory | A new `session_log_<timestamp>.json` file appears for this run; `doc/` does **not** receive any session log files | PASS (2026-04-29) |
| 2.7 | Send a second plan (e.g. `Plan a tanda of Di Sarli tangos from the 1940s`) | New tracks **append** to the existing playlist (don't overwrite); cortina row inserted between tandas | |
| 2.8 | Leave context on **Any**, type `Plan me a full milonga session` | Classifier routes to PLAN; multiple tandas across styles appear | |

---

## Test 3 — PLAN path: empty result

**Purpose:** Verify graceful handling when a planning request returns 0 tracks (genuinely unmatchable, or upstream API failure): cortina insertion is skipped, the Session Log surfaces a warning with the reason, and log messages don't claim success on failure.

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 3.1 | Set context to **Tanda Planning**, type `Plan me a tanda of rock music from 2020`, send | Chat reply: `⚠️ Couldn't find enough tracks. Try a different prompt!` | PASS (2026-04-29) |
| 3.2 | Session Log `[tanda_planner]` entry | Single warning: `Tanda 1/1 failed in X.Xs — no tracks selected (reason)`. **No** preceding info "planned" line. | PASS (2026-04-29) |
| 3.3 | Session Log `[queue_publisher]` entry | `Tanda 1 skipped (no tracks)` at warning level — not "published to queue" | PASS (2026-04-29) |
| 3.4 | Session Log `[cortina_selector]` entry | **No entry** — node was skipped because the tanda was empty | PASS (2026-04-29) |
| 3.5 | Session Log `[session_summary]` entry | `Plan complete: 0 of 1 tanda(s) succeeded.` at warning level | PASS (2026-04-29) |
| 3.6 | Full Playlist | Empty / unchanged — no fake cortina inserted | PASS (2026-04-29) |

---

## Test 4 — Q&A path

**Purpose:** Verify the RAG Q&A pipeline answers tango knowledge questions through Nancy's `fetch.py` + `query.py` (markdown → Wikipedia → LLM-only fallback).

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 4.1 | Set context to **Q&A**, type `Who is Carlos Di Sarli?` | Real biographical answer mentioning pianist / orchestra leader / 1940s / smooth style | |
| 4.2 | Type `What is the difference between tango and vals?` | Answer covers musical differences (rhythm, tempo, feel) | |
| 4.3 | Leave context on **Any**, type `What BPM is Bahia Blanca?` | Classifier routes to QUESTION; returns a number or says not found | |
| 4.4 | Session Log after questions | No `tanda_planner` / `cortina_selector` entries — Q&A doesn't trigger the planning graph | |

> If answers are empty: ChromaDB wasn't ingested. Run the ingest commands from Setup §2.

---

## Test 5 — Session Log captures user actions

**Purpose:** Verify the log records manual UI actions, not just agent events.

**Color key:** blue = manual action · amber = warning · green = decision/enhance · red = error

**Precondition:** A planned tanda exists in the playlist (run Test 2 first).

| # | Action | Expected log entry | Pass? |
|---|--------|-------------------|-------|
| 5.1 | Click ↑ on a playlist row | `Moved "<title>" up in playlist.` | |
| 5.2 | Click ↓ on a playlist row | `Moved "<title>" down in playlist.` | |
| 5.3 | Click ✕ on a playlist row | `Removed "<title>" from playlist.` | |
| 5.4 | Click **Clear** in the playlist header | `Cleared playlist (N tracks).` | |
| 5.5 | Toggle **Quality Enhance** | `Quality Enhance turned ON/OFF.` | |
| 5.6 | Change **Transition (s)** | `Transition gap set to Xs.` | |
| 5.7 | Change **Cortina (s)** | `Cortina length set to Xs.` | |
| 5.8 | All entries have a `HH:MM:SS` timestamp | every row prefixed with `HH:MM:SS` (Tina's ISO format normalized) | |

---

## Test 6 — Energy Arc chart

**Purpose:** The chart reflects real track energy values from the catalog (not the internal planning target — that was removed).

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 6.1 | Open app before any tracks added | Dashed placeholder; no dots | |
| 6.2 | After Test 2 plan | One dot per song; Y axis 0–100% | |
| 6.3 | Hover over a dot | Tooltip: Song / Style / Orchestra / Singer / Decade / Source — no raw numbers | |
| 6.4 | Dot colors | Blue filled = played · Grey filled = upcoming planned | |
| 6.5 | Manually add a track from library | New dot at that track's energy | |
| 6.6 | Play a track and check chart | Dots left of current turn blue (played); dots right stay grey | |

> All 295 catalog tracks have energy values, so the hollow-square fallback (unknown energy) shouldn't appear in normal use.

---

## Test 7 — Playback controls

**Purpose:** Transport controls work without crashing.

**Precondition:** Playlist populated.

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 7.1 | Click ▶ on a track | Track highlights; audio player loads | |
| 7.2 | ▶▶ Next | Advances to next track | |
| 7.3 | ◀◀ Prev at first track | Stays at first; no crash, no wrap | |
| 7.4 | ▶▶ Next at end of queue | Stops cleanly; no crash, no loop | |
| 7.5 | Remove the currently-playing track | Player advances to next; no crash | |

---

## Test 8 — Auto-enhance hook on PLAN

**Purpose:** When `Quality Enhance` is **ON** at PLAN time, the audio enhancement pipeline runs automatically and the player serves the processed file.

**Precondition:** MP3 files in `data/raw/` matching the catalog.

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 8.1 | Quality Enhance toggle | Defaults to **OFF** (changed 2026-04-29) | PASS (2026-04-29) |
| 8.2 | Turn toggle ON, plan a tanda | Log shows `Enhanced N tracks` after the planning succeeds | |
| 8.3 | Check `data/processed/` | New `_enhanced.wav` files appear matching the planned tracks | |
| 8.4 | Play one of those tracks | Player loads from `data/processed/`, not `data/raw/` (DevTools Network tab confirms) | |
| 8.5 | Toggle OFF, run another plan | No `Enhanced` entry; no new files in `data/processed/` | |
| 8.6 | Toggle ON → OFF → ON | Each state change appears as a blue log entry | |

---

## Test 9 — Audio Enhancement chat path (ADJUST_AUDIO)

**Purpose:** The chat accepts natural-language audio adjustment requests, routes correctly, processes target tracks, and handles edge cases (clarification, current-song rejection, reset, persistence).

**Precondition:** A planned tanda in the playlist + MP3 files in `data/raw/`.

### 9.1 Routing

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 9.1.1 | Set context to **Audio Enhancement** | Label shows `🎛 Audio Enhancement` | |
| 9.1.2 | Type any message and send | Goes straight to audio processing — no extra classifier spinner | |
| 9.1.3 | Set context to **Any**, type `the next tanda is too loud` | Classifier routes to ADJUST_AUDIO (not PLAN/QUESTION) | |

### 9.2 Standard adjustment

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 9.2.1 | Context **Audio Enhancement**, type `the next tanda is a bit too harsh`, send | Spinner: `Analyzing and enhancing audio…` | |
| 9.2.2 | After spinner | Chat reply confirms presence reduction (mentions track count, direction) | |
| 9.2.3 | `data/processed/` | Updated `_enhanced.wav` files for those tracks (newer timestamp) | |
| 9.2.4 | Session Log | Entries from `parse_request`, `measure_reference`, `compute_adjustments`, `execute_enhancement` | |
| 9.2.5 | Play the adjusted tanda | Audibly less harsh than the original | |

### 9.3 Relative constraint

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 9.3.1 | Plan a multi-tanda session | Multiple tracks in playlist | |
| 9.3.2 | Type `make the rest a bit louder` | Reply states adjusted count and notes any tracks left unchanged | |
| 9.3.3 | If some tracks were already at/above target loudness | Reply explicitly says those tracks were "left unchanged" | |

### 9.4 Reset / back to default

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 9.4.1 | After adjusting, type `back to default for the next tanda` | Spinner runs | |
| 9.4.2 | After spinner | Reply: tracks reverted to adaptive enhancement; no "louder/softer" wording | |
| 9.4.3 | Try `use original` | Same — direction=reset, re-enhanced adaptively | |
| 9.4.4 | Try `undo my changes` | Same | |

### 9.5 Current song rejection

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 9.5.1 | While a track is playing, type `this song is too loud` | Reply offers 3 numbered options: rest of session / next tanda only / cancel | |
| 9.5.2 | Reply `1` (or `apply to all after this`) | Treated as clarification; adjustment applies to all tracks after the current one | |
| 9.5.3 | Reply `3` (or `cancel`) | No adjustment; chat confirms cancellation | |

### 9.6 Clarification for ambiguous request

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 9.6.1 | Type `it sounds a bit off` | Reply asks what to adjust, with 3–4 numbered options | |
| 9.6.2 | Reply with one option (e.g. `2`) | Adjustment applied for the clarified feature | |

### 9.7 Persistence (auto_enhance ON ↔ OFF)

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 9.7.1 | With auto-enhance ON, send `more bass for the rest` | Reply notes the preference will persist for future sessions | |
| 9.7.2 | Plan a new session, auto-enhance still ON | New tracks enhanced with the bass preference applied | |
| 9.7.3 | Turn auto-enhance OFF, send another adjustment | Reply does NOT mention future sessions | |
| 9.7.4 | Plan a new session, auto-enhance OFF | New tracks enhanced with no carry-over | |

---

## Test 10 — App boots without duplicate-key errors

**Purpose:** Verify the app loads cleanly, the page renders only once per script run, and Streamlit doesn't emit `StreamlitDuplicateElementKey` errors on first load or after Streamlit's hot-reload.

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 10.1 | Cold start (`uv run streamlit run main.py`), open browser | Page renders without any error / traceback panel | PASS (2026-04-29) |
| 10.2 | Edit `atdj/ui/page_main.py` (e.g., add a comment), save | Streamlit auto-reloads cleanly; no duplicate-key error appears | PASS (2026-04-29) |
| 10.3 | Send a chat message and trigger a rerun mid-edit | No duplicate-key error after the rerun | PASS (2026-04-29) |

> Background: previously `app.py` had a module-level `run_app()` call AND `main.py` called `run_app()` — so the page rendered twice per script run, causing intermittent duplicate-key errors on every widget (`sb_provider`, `sb_model`, etc.). The module-level call was removed.

---

## Test 11 — Sidebar settings

**Purpose:** Provider/model/key changes propagate without a restart.

| # | Action | Expected | Pass? |
|---|--------|----------|-------|
| 10.1 | Open sidebar | Settings panel visible (no Sessions list above it) | |
| 10.2 | Change Provider to Gemini | Model dropdown updates to Gemini models | |
| 10.3 | Paste a key, click Save Settings | Toast "Settings saved.", no crash | |
| 10.4 | Send a chat request | Uses the newly selected provider (visible in any failure message via the diagnostic suffix) | |
| 10.5 | Switch back to Claude | Claude models shown; prior chat history unaffected | |

---

## Pass/Fail summary

| Test | Description | Status |
|------|-------------|--------|
| 1 | Fresh start state | PASS (2026-04-29) |
| 2 | PLAN path — happy path | PASS (2026-04-29) |
| 3 | PLAN path — empty result | PASS (2026-04-29) |
| 4 | Q&A path | |
| 5 | Session Log — user actions | |
| 6 | Energy Arc chart | |
| 7 | Playback controls | |
| 8 | Auto-enhance hook on PLAN | partial (8.1 PASS) |
| 9 | Audio Enhancement chat path | |
| 10 | App boots without duplicate-key errors | PASS (2026-04-29) |
| 11 | Sidebar settings | |

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
| `back to default` triggers a planning response | Classifier routed to PLAN | Set context dropdown to **Audio Enhancement** to bypass the classifier |
| Clarification question, then second message starts a new request | `pending_adjustment` cleared by a page reload | Don't reload mid-clarification; resend the original |
| Gemini 429 visible in terminal | Rate limit during Q&A | Normal — Claude fallback runs automatically; the Q&A answer still returns |
