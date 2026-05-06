# Demo Proposal — AT-DJ

A live demo of one of two paths (the team picks the path on the day, recordings are fallback):

- **Recording A — Claude** (no Lyria, cortinas from local pool)
- **Recording B — Gemini** (Lyria-generated cortinas; full session is the last action)

Total demo budget: **≤ 4:30** wall-clock for the timed segments. Pre-warm runs off-clock and is NOT in the recording — `record_with_audio.py` waits for the demo harness to print `TIMED RUN STARTS` before starting ffmpeg.

---

## 1. Warm-up (off-clock — not recorded)

Three chat sends + a media pause, all done by `setup()` in `demo_script.py`:

1. **PLAN single**: `Plan a Di Sarli tanda from the 1940s.`
2. **Q&A**: `Tell me about Carlos Gardel.`
3. **Audio Enhancement**: click play on first track, ⏭ to track 2, send `Make this song's loudness softer.`, reply `1` (rest of session). DSP runs on the warm-up tanda — loads `librosa`, `noisereduce`, `pedalboard`, `pyloudnorm`, `soundfile`.
4. **Pause audio iframe** via `postMessage 'atdj-pause'` so the recording opens in silence with the warm-up chat + playlist visible as background context.

Different orchestras / Q&A topic from the demo so the chat content is visibly distinct from the timed run's prompts.

---

## 2. Recording A — Claude (pool fallback)

**Configuration.** Provider = Claude; `GEMINI_API_KEY` commented in `.env` so cortinas come from `data/cortinas/`. Full-session PLAN runs INTERLEAVED.

**File.** `doc/demo/_rehearsal_artifacts/at_dj_demo_claude_<timestamp>.mp4`

| # | Action | Prompt / click | Speech |
|---|---|---|---|
| 1 | Sidebar visible (~4 s) → click collapse → 3-mode intro | (no chat) | "API key, provider, and model are pre-set in the sidebar. AT-DJ is an AI tango DJ driven by chat — three modes (PLAN, Q&A, Audio Enhancement) plus cortina generation, all behind one router with shared typed state." |
| 2 | PLAN single, then scroll FULL PLAYLIST into view so the audience sees the just-generated tanda listed (4 tracks + closing cortina); click ▶ on first track (~6 s music) | `Plan a Pugliese tango tanda from the 1940s.` | "Let me plan something. *Plan a Pugliese tango tanda from the 1940s.* And here's the result in the Full Playlist — four Pugliese tracks plus a closing cortina. Let me play the first one." |
| 3 | Send full-session prompt; while it generates, scroll Energy Arc into view, then Session Log into view, then back to Full Playlist (so the audience sees the just-generated full session populating) | `Plan a full session following traditional structure — romantic 1940s, smooth and elegant.` | "And the headline. *Plan a full session…* Six tanda slots in a fixed schema, cortinas between them. While that generates: **Energy Arc** is the planned energy curve, dot per track. **Session Log** captures every action — colour-coded by severity, icons by source. And here in the **Full Playlist** is the result — 22 tracks across 6 tandas with cortinas between them, all rule-compliant." |
| 4 | Click cortina row's ▶ — brief audible cortina (~6 s) | (click ▶ on cortina row) | "Let's hear a cortina. Pool-selected, matched on BPM and energy to the preceding tanda — the genre shift is the signal for dancers to change partners." |
| 5 | Q&A; after reply lands, scroll WITHIN chat container so user question + start of answer are visible together; then scroll back to bottom | `What characterizes Pugliese's style?` | "Q&A is a separate subgraph. Two retrieval paths — local curated knowledge base first, Wikipedia fallback, LLM-only last. Pugliese lives in our RAG, so the answer is grounded there." |
| 6 | Skip ⏭ off the cortina; send adjust trigger; menu lands; reply free-form (no menu number) | trigger: `Make this song's bass louder.` <br>reply: `next 1 song` | "Audio enhancement. *Make this song's bass louder.* — feature=bass, scope=current. Current is contentious because the file is actively streaming, so the agent surfaces a menu. Instead of picking a number, I just type *next 1 song* in plain English. The agent drops the menu, re-parses, runs DSP on one upcoming track. Plain English is enough." |

[End of demo. Switch to slides.]

---

## 3. Recording B — Gemini (Lyria path)

**Configuration.** Provider = Gemini; `GEMINI_API_KEY=` uncommented in `.env`. Cortinas are LLM-prompted Lyria audio. Full-session PLAN is the LAST live action (Lyria adds ~30–60 s × 5 cortinas ≈ 3–5 min total).

**File.** `doc/demo/_rehearsal_artifacts/at_dj_demo_gemini_<timestamp>.mp4`

| # | Action | Prompt / click | Speech |
|---|---|---|---|
| 1 | Sidebar visible (~4 s) → click collapse → 3-mode intro | (no chat) | "API key, provider, and model are pre-set in the sidebar. AT-DJ is an AI tango DJ driven by chat — three modes (PLAN, Q&A, Audio Enhancement) plus cortina generation, all behind one router with shared typed state." |
| 2 | PLAN single (Lyria called for the closing cortina — ~30–60 s extra wait); scroll FULL PLAYLIST into view so the audience sees the just-generated tanda listed (4 tracks + Lyria cortina); click ▶ on first track (~6 s music) | `Plan a Pugliese tango tanda from the 1940s.` | "*Plan a Pugliese tango tanda from the 1940s.* This is the Lyria path — the closing cortina is being generated on demand, so this takes a bit longer. And here's the result — four Pugliese tracks plus a Lyria-generated cortina at the end. Let me play the first track." |
| 3 | Click cortina row's ▶ — Lyria-generated cortina plays (~6 s audible) | (click ▶ on cortina row) | "Here's the Lyria-generated cortina. The LLM crafted a music prompt from the tanda's mood and energy summary — no bandoneon, no tango compás, BPM matched — and Lyria synthesised this 25-second clip on demand." |
| 4 | UI panel tour: scroll Energy Arc into view; then scroll Session Log into view; then scroll back to Now Playing | (no chat) | "Two key panels: **Energy Arc** is the planned energy curve, dot per track — filled circle = played, hollow = upcoming, square = cortina. **Session Log** below the chat captures every agent and user action, timestamped and colour-coded by severity — blue = agent, grey = user, amber = warning, red = error." |
| 5 | Q&A; after reply lands, scroll WITHIN chat container so user question + start of answer are visible together; then scroll back to bottom | `What characterizes Pugliese's style?` | "Q&A is a separate subgraph. Two retrieval paths — local curated knowledge base first, Wikipedia fallback, LLM-only last resort. Pugliese lives in our RAG, so the answer comes from there. Note Gemini Q&A is slower than Claude — typically ~50 s." |
| 6 | Skip ⏭ off the cortina; send adjust trigger; menu lands; reply free-form `next 1 song` | trigger: `Make this song's bass louder.` <br>reply: `next 1 song` | "Audio enhancement. *Make this song's bass louder.* — feature=bass, scope=current. Current is contentious because the file is actively streaming, so the agent surfaces a menu. Instead of picking a number, I just type *next 1 song* in plain English. The agent drops the menu, re-parses, runs DSP on one upcoming track. Plain English is enough." |
| 7 | Fire full-session PLAN as the LAST live action; do NOT wait — switch to slides immediately. Lyria takes ~3–5 min for 5 cortinas, generates during the slide block | `Plan a full session following traditional structure — romantic 1940s, smooth and elegant.` | "Last live action — kicking off the full session. With Lyria generating each cortina on demand, this takes a few minutes. We'll switch to slides now and come back at the end to hear the result." |

[After slide block, navigate back to the app. Show the populated playlist with Lyria cortinas.]

---

## 4. Comparison

| Action | Claude (A) | Gemini (B) |
|---|---|---|
| PLAN single tanda | ~10 s | ~30–60 s (Lyria call for closing cortina dominates) |
| PLAN full session | ~30 s (pool cortinas) | ~3–5 min (Lyria × 5 cortinas — fired last) |
| Q&A | 17–27 s | ~50 s |
| Audio Enhancement (menu + free-form + DSP) | 21–70 s with DSP pre-warm; can stretch to 100–120 s on long chat history | TBD |
| Cortina audible playback | ~10 s | ~10 s |
| **Total demo (timed segments)** | **3:32 observed** (range 3:30–4:45) | **~4:00–4:30** (full session runs during slides, not timed) |

---

## 5. Out-of-script scenarios

NOT in either recording. Pre-record as 60–90 s screencasts to drop in for slides or Q&A.

| Scenario | Trigger | What it shows |
|---|---|---|
| Audio Enhancement — clarification node | `Fix the audio.` | Vague request → 4-option clarification menu. |
| Audio Enhancement — reset flow | `Reset everything to default.` | Reset path: deletes processed files, restores originals. |
| Audio Enhancement — specific-track scope | `Make the second song of the next tanda louder.` | Scope=specific resolution by track index. |
| Audio Enhancement — cancel mid-flow | trigger menu, reply `3` | Cancel terminal node, no DSP. |
| Audio Enhancement — off-topic interrupt | trigger clarification, then `Plan a Demare tanda` | Menu dropped, message re-routed through classifier. |
| Cortina generator close-up | full-session prompt, then point at one cortina | Show the LLM-crafted music_prompt that fed Lyria. |
| Skip-to-next-tanda | manual jump button mid-tanda | Manual control coexists with agent autonomy. |
| Session log replay | Plan + adjust + replan, open the JSON log | Every node-level event captured for replay/audit. |

---

## Recording / dry-run mechanics

```
# rehearse only (no MP4)
DEMO_PROVIDER=Claude  uv run python doc/demo/demo_script.py
DEMO_PROVIDER=Gemini  uv run python doc/demo/demo_script.py

# produce a shareable MP4 with audio
DEMO_PROVIDER=Claude  uv run python doc/demo/record_with_audio.py
DEMO_PROVIDER=Gemini  uv run python doc/demo/record_with_audio.py
```

`demo_script.py` reads `DEMO_PROVIDER`, switches the sidebar provider, fills the right API-key field, and applies the right ordering (interleaved vs full-session-last) automatically. Output filenames are tagged with the provider.

For voice narration on top of music, run `demo_script.py` headed and capture screen externally with **OBS** or **Game Bar** (`Win + G`).

See `recording_notes.md` for debugging history and rerun notes.
