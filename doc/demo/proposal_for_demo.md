# 5-Minute Demo Proposal — AT-DJ

A latency-grounded script for the in-class live demo. Walks through PLAN → ADJUST_AUDIO (focus) → Q&A in five minutes flat, with fallback ordering and prompt options pre-rehearsed.

---

## Latency data this plan is built on

Pulled from `tests/UI_TEST_GUIDE.md` (measured 2026-04-29 to 2026-05-01). Per-action overhead:

| Action | Wall clock | Source |
|--------|------------|--------|
| Streamlit "user message paints + Working on it…" warm-up after each send | ~6s | Test 11.4 note |
| PLAN single tanda — Pugliese 1940s | 7.9s | Test 2.1 |
| PLAN single tanda — Di Sarli 1940s (second send) | 6.7s | Test 2.7 |
| PLAN after Clear — D'Arienzo | 5.6s | Test 2.9 |
| PLAN multi-tanda "full milonga session" | 33.8s | Test 2.8 — ⚠️ skip live |
| Q&A — orchestra biography (Claude) | 14.4–18.8s | Tests 4.1–4.3 |
| Q&A via Gemini | ~50s | Test 11.4 — ⚠️ avoid |
| ADJUST routing + standard adjustment ("the current tanda…") | 16.5–17.0s | Tests 9.1.1, 9.2.1 |
| ADJUST current-song rejection menu | 16.4s | Test 9.5.1 |
| ADJUST cancel via "3" | 11.2s | Test 9.5.3 |
| ADJUST clarification opener "it sounds a bit off" | 14.9s | Test 9.6.1 |
| ADJUST clarification reply ("too loud" / "1") | 11.6–12.9s | Tests 9.6.2, 9.6.2b |
| ADJUST off-topic-during-clarification recovery | 36.3s | Test 9.6.3 — ⚠️ avoid |
| ADJUST reset ("back to default for the next tanda") | 9.1s | Test 9.4.1 |
| Slider / UI controls | 0.9–2.5s | Tests 5.x, 7.x |

**Implications baked into the script:**
- **Use Claude as the provider** — Gemini Q&A at ~50s blows the budget alone.
- Each chat send costs ≥6s of UI warm-up before the LLM even starts.
- A 4-track tanda's audio enhancement processing (post-LLM) is in the same order of magnitude as the LLM call. Budget extra for it.
- Avoid: `"Plan me a full milonga session"` (33.8s), Gemini provider for Q&A (~50s), off-topic during clarification (36.3s).

---

## Pre-demo setup (off-clock)

Before stepping on stage:
- Open the app and complete the **3-step provider setup** in the sidebar: pick **Claude**, pick a Claude model, paste the Anthropic key, click **Save Settings**.
- **Collapse the sidebar** after Save Settings (click the `<<` button at the top of the sidebar). The main panels need the full screen width during the demo, and the Anthropic key shouldn't be on screen.
- **Pre-warm** by sending one PLAN request and one trivial Q&A, then **Clear**. This caches the Claude client, the RAG indexes, and the Streamlit fragments.
- Have the chat panel + Now Playing + Full Playlist + Session Log all visible simultaneously.
- Test audio output at a moderate volume.
- Confirm `data/raw/` and `data/processed/` exist and contain audio for the orchestras you'll plan.

---

## Primary script (4:40 budget + 20s buffer = 5:00)

> **Constraint that drove the script:** the multi-tanda detector in `page_main.py` only triggers on a narrow keyword list (`session`, `full`, `complete`, `tonight`, `milonga night`). A natural "plan X tanda then Y tanda" phrasing is parsed as a single tanda; using one of the keywords flips the system into a 29-track full-milonga path that takes ~40s to plan and overwhelms the demo. There is no in-between today, so the live script uses **one tanda** and the rejection-menu reply *"Apply to all songs after this one (rest of session)"* to enhance the remaining tracks. The talking point — *"current track is read-only, the correction applies to upcoming tracks"* — lands either way; only the scope label changes.

| Time | Segment | Action | Notes |
|------|---------|--------|-------|
| 0:00–0:25 | Frame | "AT-DJ is an AI tango DJ with three modes: PLAN, Q&A, ADJUST_AUDIO. Today's focus is the audio-adjustment loop." Point at panels. | Pure narration |
| 0:25–1:10 | PLAN (1 tanda) | Type the PLAN prompt; ~6s warm-up + ~12s LLM + ~25s narrate while watching the 4 tracks and the cortina row appear. | Plans one Pugliese tanda (4 tracks). Measured ~30s end-to-end on cold start. |
| 1:10–1:35 | Music starts | Click ▶ on track 1; let ~20s play; click ⏭ to advance to track 2. | Audience hears tango; establishes the "before" sound. The ⏭ moves us inside the same tanda so 2-3 tracks remain after the cursor for the adjustment to land on. |
| 1:35–2:50 | ADJUST scenario — rejection menu, full circle | Type "Make this song louder." (5s) + warm-up (6s) + rejection menu reply (~10s) + read menu (8s) + reply "1" (3s) + warm-up (6s) + apply enhancement on the rest of the tanda (~25s, DSP on 2-3 tracks) + read confirmation (5s). | Showcases the design intent: current track is read-only; correction applies to the upcoming tracks of the rest of the session. |
| 2:50–3:15 | Audible result + narration | Skip ⏭ into a now-enhanced track; let 10s play; narrate the difference. | The payoff: audience HEARS the change. |
| 3:15–3:55 | Q&A (single round-trip) | Type one short question (5s) + warm-up (6s) + answer (~17s) + read (12s). | Demonstrates the third mode. |
| 3:55–4:40 | Session log + wrap | Point at the Session Log panel; call out the structured entries (📋 PLAN summary, 🎛 AUDIO summary). One sentence: "Everything the agent did is logged for replay." | Shows engineering rigor. |
| 4:40–5:00 | Buffer | 20s slack for one segment running long, or audience reaction. | |

Measured wall-clock from the rehearsal harness on a cold-start run: **3:33** total — comfortably under the 4:40 budget, with the buffer absorbing per-segment overshoot.

---

## Prompt options (pick one per segment)

**PLAN segment (1 tanda)** — pick one.
- A. `"Plan a Pugliese tango tanda from the 1940s."` — measured ~30s end-to-end including warm-up; reliably produces 4 Pugliese tracks. **Recommended**.
- B. `"Plan a Di Sarli tanda from the 1940s."` — same shape; Di Sarli's smoother style contrasts more obviously with audio adjustment.
- C. `"Plan a short milonga tanda."` — fastest cache; rhythmically punchy but less dramatic for an audio-adjust demo.

⚠️ **Avoid these phrasings:**
- *"Plan me a full milonga session"* — triggers the full-milonga path, plans ~29 tracks at ~40s LLM cost. Eats the ADJUST_AUDIO budget alone.
- *"Plan X then Y tanda"* — natural English but does NOT produce 2 tandas (the detector keys on `session`/`full`/`complete`, not on natural conjunction). You will get a single tanda, which makes reply *"next tanda only"* land on the no-targets terminal.

**ADJUST scenario — rejection-menu trigger** (the message that starts the round-trip), pick one:
- A. `"Make this song louder."` — explicit *this song*; cleanest scope=current trigger. **Recommended**.
- B. `"The current track sounds a bit muddy, fix it."` — natural phrasing; also triggers rejection.
- C. `"Boost the bass on the playing song."` — same trigger, lets you say *"feature=bass"* if asked about parsing.

**Reply to the rejection menu** — what to type after the menu appears:
- **"1"** — *Apply to all songs after this one (rest of session)*. **Recommended for the current single-tanda script** because it always has real targets (the remaining 2-3 tracks of the tanda), so DSP actually runs.
- ⚠️ Do **not** use **"2"** (*Apply to the next tanda only*) with the recommended single-tanda PLAN — there is no next tanda, so the agent terminates at the no-targets node with *"No tracks found matching that description after the current position."* and the demo's payoff segment goes silent.
- *"2"* becomes the right pick again **only if** a future change extends the multi-tanda detector or the demo plans two tandas via two separate PLAN messages.
- **"3"** / *"cancel"* — terminates with no side effect; only useful for demonstrating the cancel path as a separate spotlight.

**Q&A segment** — pick one. All measured against Claude.
- A. `"What characterizes Pugliese's style?"` — RAG tango knowledge; ~17s. **Recommended**.
- B. `"Tell me about Di Sarli."` — ~17s; safe and short.
- C. `"What BPM is Bahia Blanca?"` — 14.4s, shortest measured Q&A. Use if time-pressed.

⚠️ Don't ask `"Why did you choose this cortina?"` — recent-context grounding is unproven (see `doc/future_work.md` §5); risk of an unhelpful answer mid-demo.

---

## Backup / fallback (if a segment must be cut)

Drop in this order if running long at 3:00:
1. Skip the audible-result narration (2:50–3:15) — say "and you'd hear the difference here" while moving on. Saves ~25s.
2. Skip Q&A entirely (3:15–3:55) — narrate "we also support open Q&A about tango". Saves ~40s.
3. Skip the session-log wrap (3:55–4:40) — describe instead of click. Saves ~30s.

(All three combined buy ~95s of slack — comfortably enough to recover from one slow LLM call.)

If something fails on stage:
- **PLAN fails / LLM times out** → switch to the pre-recorded screencast (see spotlights). Narrate from slides while it plays.
- **Audio enhancement processing fails** ("No tracks to adjust" warning surfaces) → narrate the design ("the agent measures the current track as a reference and applies the delta to upcoming tracks"); show the rejection menu screenshot from `tests/UI_TEST_GUIDE.md` Test 9.5.1.
- **Audio doesn't play** → keep speaking; show chat transcript + Full Playlist; explain what would have played.

---

## Validation step before demo day

The latency math above has been verified end-to-end by the rehearsal harness `doc/demo/demo_script.py`. To re-validate before stage time:

1. Start the app: `uv run streamlit run main.py --server.headless true --server.port 8501`.
2. Run `uv run python doc/demo/demo_script.py`. The script drives Playwright through the same chat sequence the live demo uses, prints a per-segment wall-clock timestamp, and flags any segment that exceeds budget.
3. Aim for the harness to complete in ≤4:40 with the recommended prompts. The last verified cold-start run came in at 3:33.
4. If a segment overruns by >15s, swap to the next-fastest prompt option for that segment (A → C in the lists above) and rerun.
5. Run the harness at least twice the day before — once cold (fresh Streamlit) and once warm — to see the spread.

### Recording with audio (music)

Playwright's built-in `record_video_dir` captures **video frames only**. To produce a recording with the music audible, use the orchestrator script `doc/demo/record_with_audio.py`. It:

1. Starts a WASAPI loopback recorder in a background thread (captures whatever your default speaker is playing — the actual demo music).
2. Runs `demo_script.py` with `HEADLESS = False` so a real Chromium window opens on your desktop and audio plays through your speakers.
3. Stops the audio recorder when the demo exits.
4. Muxes Playwright's silent video and the captured audio into a single `.mp4` under `_rehearsal_artifacts/`.

Prerequisites: `ffmpeg` on PATH (winget install Gyan.FFmpeg) and the Python `soundcard` package (already in `pyproject.toml`).

Run:
```
uv run streamlit run main.py --server.headless true --server.port 8501
uv run python doc/demo/record_with_audio.py
```

The final file is named `at_dj_demo_<timestamp>.mp4`.

### Recording with voice narration

For voice on top of the music, two options:

- **Live**: instead of `record_with_audio.py`, run the bare `demo_script.py` and capture the screen externally with **OBS Studio** (recommended — captures window + desktop audio + microphone in one go) or **Windows Game Bar** (`Win + G`, microphone capture enabled in Settings → Gaming → Captures).
- **Post-hoc**: record the silent or audio-only output from the orchestrator, then overlay narration in any video editor (Shotcut, DaVinci Resolve free, Windows Photos).

For demo day itself, recording isn't required — you'll be running live. The recording is the fallback in case something fails on stage.

---

## Feature spotlights NOT included in the live 5-min script

The integrated 5-min script is primary. These spotlights are NOT performed live but are documented (and ideally pre-recorded as 60–90s screencasts) so they can be: (a) shown as fallback if a live segment fails, (b) referenced in Q&A, or (c) embedded in slides.

Each spotlight, what it demonstrates, suggested prompt, and recommended fallback use:

- **Audio adjust — reset flow** (~60s) — `"Reset everything to default."` Shows the reset path (delete processed files, restore originals). *Use as fallback if the live ADJUST scenario breaks.*
- **Audio adjust — specific-track scope** (~75s) — `"Make the second song of the next tanda louder."` Shows scope=specific resolution by track index/name. *Use as fallback or in Q&A if asked "can you target one song?"*
- **Audio adjust — clarification node** (~90s) — `"Fix the audio."` Walks through the clarification menu (the option pruned from the live script for time). *Use in Q&A if asked about ambiguous-input handling.*
- **Cortina selector** (~75s) — Plan a tanda; ask `"Why did you pick that cortina?"` *Use as fallback if PLAN segment runs short, or in Q&A if asked about the cortina logic.*
- **Session log redesign** (~60s) — Plan + adjust + replan, then open the session log to show the structured activity timeline. *Use as fallback if the wrap segment is cut for time.*
- **Skip-to-next-tanda** (~45s) — Click the manual jump button mid-tanda; show that the planning agent state stays consistent. *Use in Q&A if asked about user controls vs. agent autonomy.*

**Pre-record action**: aim to capture at least the first three above as `.mp4` screencasts (use Windows Game Bar `Win+G` or OBS) before demo day, so they're ready to drop in.

---

## See also

### Script files in this folder

Two Python files do the work; they have different jobs.

- **`demo_script.py`** — the *driver*. Opens a Chromium window, sets it on the laptop screen, fills the API key, sends the chat messages and clicks the playback buttons in the right order. Times each segment against the budget. Use it on its own when you just want to **rehearse** the demo flow without producing a recording (it can optionally record silent video via Playwright's built-in recorder, but that's it).
- **`record_with_audio.py`** — the *orchestrator*. Spawns `demo_script.py` and, in parallel, records the screen pixels (via `ffmpeg gdigrab`) and the system audio (via WASAPI loopback). When the demo finishes, it muxes the video and audio into a single MP4. Use it when you want a **shareable recording with sound**.

Rule of thumb: dry-run with `demo_script.py`, produce the deliverable with `record_with_audio.py`.

- [`recording_notes.md`](recording_notes.md) — debugging history, configuration knobs, and pitfalls hit while making the recording. Read this first if a re-recording attempt fails.
