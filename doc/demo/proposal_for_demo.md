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
- **Pre-warm** by sending one PLAN request and one trivial Q&A, then **Clear**. This caches the Claude client, the RAG indexes, and the Streamlit fragments.
- Have the chat panel + Now Playing + Full Playlist + Session Log all visible simultaneously.
- Test audio output at a moderate volume.
- Confirm `data/raw/` and `data/processed/` exist and contain audio for the orchestras you'll plan.

---

## Primary script (4:50 + 10s buffer = 5:00)

| Time | Segment | Action | Notes |
|------|---------|--------|-------|
| 0:00–0:25 | Frame | "AT-DJ is an AI tango DJ with three modes: PLAN, Q&A, ADJUST_AUDIO. Today's focus is the audio-adjustment loop." Point at panels. | Pure narration |
| 0:25–1:10 | PLAN (2 tandas) | Type prompt option A or B; ~6s warm-up + ~14s LLM (2 × ~7s) + ~25s narrate while watching the playlist + cortina row appear. | Plans 2 tandas so "next tanda" exists for the rejection-menu scenario |
| 1:10–1:35 | Music starts | Click ▶ on track 1; let ~20s play; click skip-to-end-of-current-tanda so we arrive at the second tanda's first track. | Audience hears tango; establishes the "before" sound |
| 1:35–2:50 | ADJUST scenario — rejection menu, full circle | Type "Make this song louder." (5s) + warm-up (6s) + reply with menu (16.4s) + read menu (8s) + reply "2" (3s) + warm-up (6s) + apply enhancement on next tanda (~25s including DSP on 4 tracks) + read confirmation (5s). | Showcases the design intent: current track is read-only reference; corrections apply to upcoming tracks |
| 2:50–3:15 | Audible result + narration | Skip into the now-enhanced next tanda; let 10s play; narrate the difference. | The payoff: audience HEARS the change |
| 3:15–3:55 | Q&A (single round-trip) | Type one short question (5s) + warm-up (6s) + answer (~17s) + read (12s). Use prompt option A or C. | Demonstrates the third mode |
| 3:55–4:40 | Session log + wrap | Open the Session Log panel; point out the structured entries (📋 PLAN summary, 🎛 AUDIO summary). One sentence: "Everything the agent did is logged for replay." | Shows engineering rigor |
| 4:40–5:00 | Buffer | 20s slack for one segment running long, or audience reaction. | |

---

## Prompt options (pick one per segment)

**PLAN segment (2 tandas)** — pick one. Tested latencies in parens.
- A. `"Plan a Pugliese tango tanda from the 1940s, then a D'Arienzo tango tanda."` — both orchestras have measured PLAN latencies (7.9s + ~7s). **Recommended**.
- B. `"Plan a Di Sarli tanda then a Pugliese tanda, both from the 1940s."` — Di Sarli 6.7s, Pugliese 7.9s, audibly different so the contrast lands.
- C. `"Plan two short milonga tandas."` — fastest if both come back from cache; rhythmically distinctive but less dramatic an "audio adjust" demo because milongas are already punchy.

⚠️ Don't use `"Plan me a full milonga session"` — measured at 33.8s, eats the ADJUST_AUDIO budget.

**ADJUST scenario — rejection-menu trigger** (the user message that starts the round-trip), pick one:
- A. `"Make this song louder."` — explicit "this song"; cleanest scope=current trigger. **Recommended** for clarity.
- B. `"The current track sounds a bit muddy, fix it."` — natural phrasing; also triggers rejection.
- C. `"Boost the bass on the playing song."` — same trigger, lets you say "feature=bass" if asked about parsing.

**Reply to the rejection menu**, pick one:
- "2" (numeric form) — covered by Test 9.5.2b, shortest to type. **Recommended**.
- "Apply to the next tanda only" (text form) — covered by Test 9.5.2; demonstrates the heuristic substring matching.

(Don't use "1" / "Apply to all songs after this" because then DSP runs on every remaining track, which slows the demo. The "next tanda only" path enhances 4 tracks.)

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

The latency math above is from real measurements but stitched together — actual back-to-back behaviour may differ. Suggested dry-run protocol:

1. Run the rehearsal harness `doc/demo/demo_script.py` end-to-end on the laptop you will demo from. The script drives Playwright through the same chat sequence and prints a per-segment wall-clock timestamp so any segment that exceeds budget is visible at a glance.
2. Aim for the harness to complete in ≤4:50 with the recommended prompts (`A`/`A`/`A`/`A`).
3. If a segment overruns by >15s, swap to the next-fastest prompt option for that segment (A → C in the lists above) and rerun.
4. Run the harness at least twice the day before — once cold (no warm-up done) to measure first-call latency, once after warm-up to measure the steady-state numbers the live demo will see.

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
- [`demo_script.py`](demo_script.py) — Playwright rehearsal harness for the script above.
