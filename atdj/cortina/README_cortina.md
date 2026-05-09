# `atdj/cortina/` — Cortina Generation & Selection

This directory handles one of AT-DJ's four core GenAI capabilities: **generating cortinas that bridge consecutive tandas**. A cortina is a short (~25–30 second) non-tango musical interlude placed between every tanda at a milonga. Its job is purely structural — it signals to dancers that a tanda has ended and it's time to switch partners. The floor clears, then the next tanda begins.

---

## What Is a Cortina, and Why Does It Matter?

A milonga's structure depends entirely on dancers reading the music. When tango plays, you stay with your partner. When non-tango music plays — the cortina — the floor clears. This isn't optional: a cortina that sounds too much like tango confuses dancers; one that feels tonally disconnected from what just played creates a jarring transition.

AT-DJ's cortina system takes this seriously. Rather than playing the same generic clip between every tanda, it generates or selects a cortina that:
- **Matches the energy and BPM** of the preceding tanda so the transition feels natural on the dance floor
- **Uses a random non-tango genre** (jazz, bossa nova, soul, funk, etc.) so cortinas are clearly non-tango but varied
- **Has no bandoneon, no tango rhythm, no compás** — the three hard rules that must be satisfied for a cortina to function as a partner-change signal

---

## How It Fits Into the System

The cortina subsystem connects to the LangGraph agent, the Streamlit UI, and the audio data layer:

```
tanda_planner node
        │
        │ (needs_cortina = True after every successful tanda)
        ▼
cortina_selector node  ──► tools.py: select_cortina
        │
        ├── 1. Try Lyria (Gemini key present)
        │       └── generator.py: generate_cortina()
        │               ├── _summarize_tanda()       ← feature extraction from prev tanda tracks
        │               ├── _craft_music_prompt()    ← LLM writes a music generation prompt
        │               └── _call_lyria()            ← Lyria streams a fresh ~25s audio clip
        │
        ├── 2. Fallback: pool selection (Lyria unavailable / API error)
        │       └── pool.py: find_best_cortina()
        │               ├── build_pool_features()    ← BPM + energy for each clip in pool (cached)
        │               └── scoring + random top-3   ← pick best match, add variety
        │
        └── 3. Silent placeholder (pool empty)
                └── {"type": "cortina", "title": "Cortina", "duration": "0:20"}

        ▼
queue_publisher node  →  live_queue in Streamlit session state  →  DJ Console UI
```

The agent state field `needs_cortina` acts as the trigger: `tanda_planner` sets it to `True` whenever it successfully selects tracks, and `cortina_selector` resets it to `False` after placing a cortina. The LangGraph router uses this flag for conditional routing: `needs_cortina → cortina_selector`.

---

## Script Reference

### `generator.py` — Lyria-Powered Cortina Generation

**What it does:** Generates a fresh, unique cortina audio clip for each tanda transition using a two-step pipeline: an LLM writes a music generation prompt tailored to the preceding tanda's sound, then Google's Lyria model synthesizes the actual audio from that prompt.

**Public API:**
```python
generate_cortina(
    prev_tracks: list[dict],   # track dicts from the preceding tanda
    next_style: str | None,    # style of the upcoming tanda ("tango", "vals", "milonga"), or None for closing
    output_dir: Path,          # where to save the generated .wav / .mp3
    api_key: str,              # Google Gemini API key (required for Lyria)
) -> dict                      # playlist item dict: type, title, file_path, duration, source, music_prompt
```

**Pipeline — three internal steps:**

#### Step 1: `_summarize_tanda(tracks)` — Feature Extraction
Reads the preceding tanda's track metadata and computes aggregate features used to describe the just-finished sound:
- **Dominant style** — most common style across all tracks
- **Orchestra and decade** — taken from the first track
- **Average energy** — mean across tracks; bucketed into `"low"` / `"moderate"` / `"high"`
- **Average BPM** — rounded mean across tracks
- **Derived mood** — inferred from style × energy combination:

| Style | Energy | Mood |
|---|---|---|
| Milonga | high | playful and festive |
| Milonga | low | light and rhythmic |
| Vals | low/mid | romantic and flowing |
| Vals | high | elegant and sweeping |
| Tango | high | dramatic and intense |
| Tango | low | melancholic and tender |
| Tango | moderate | expressive and danceable |

#### Step 2: `_craft_music_prompt(prev, next_style)` — LLM Music Prompt Writing
Calls the configured LLM (Gemini or Claude, via `get_ui_llm()`) with a structured instruction that:
- Describes the tanda that just played (energy, mood, style, orchestra, decade, BPM)
- Names the upcoming tanda style if known
- Instructs the model to pick **one genre randomly** from: jazz, bossa nova, soul, funk, pop, electronic, classical, blues, reggae, cinematic orchestra, lo-fi
- Enforces the hard rules: no bandoneon, no tango rhythm, energy must match the tanda, BPM must stay close to the tanda's tempo

The model returns a 2–3 sentence music description in plain musical terms — no markdown, no explanation. This becomes the Lyria prompt.

#### Step 3: `_call_lyria(music_prompt, output_path, api_key)` — Audio Synthesis
Calls `google-genai` with model `"lyria-3-clip-preview"`, streams the response in chunks, and writes the raw audio bytes to disk. The file extension is inferred from the returned MIME type. Raises `RuntimeError` if Lyria returns no audio data.

**Returns** a playlist-ready dict:
```python
{
    "type": "cortina",
    "title": "Cortina (tango → vals)",
    "file_path": "/path/to/cortina_a3f1bc2d.wav",
    "duration": "0:25",
    "source": "generated",
    "music_prompt": "A smooth bossa nova trio...",
}
```

**Design notes:**
- Each cortina gets a unique UUID-derived filename so no two generated clips overwrite each other
- `next_style=None` means a closing cortina (end of session) — the prompt omits the "next tanda" framing
- The genre randomization instruction is explicit in the prompt to prevent the LLM from defaulting to the same genre every time

---

### `pool.py` — Pre-Licensed Fallback Selector

**What it does:** When Lyria is unavailable (no Gemini API key, or Lyria call fails), `pool.py` picks the best matching cortina from a local folder of pre-licensed non-tango audio clips. It scores each clip against the preceding tanda's BPM and energy and picks from the top 3 candidates randomly to add variety.

**Pool location:** `data/cortinas/` — place `.mp3` or `.wav` files here. The pool can contain any non-tango music clips of roughly 30 seconds.

**Public API:**

#### `build_pool_features(force=False)` → `pd.DataFrame`
Runs once (or when `force=True`) to extract BPM and energy from every audio file in the pool using librosa, and saves results to `data/cortinas/pool_features.csv`. Subsequent calls load from the cached CSV.

```python
# BPM: librosa beat tracker
# Energy: RMS mean, normalized to [0, 1] with ceiling at 0.3 RMS
```

Called automatically by `find_best_cortina()` if the CSV doesn't exist yet.

#### `find_best_cortina(tanda_summary, exclude)` → `dict`
Selects the pool clip that best matches the tanda's sound profile.

**Scoring formula** (lower = better match):
```
score = 0.7 × |clip_bpm - tanda_bpm| / 60
      + 0.3 × |clip_energy - target_energy|
```

BPM difference is weighted 70% because tempo continuity is the most physically noticeable feature on the dance floor. Energy is weighted 30%.

**Selection:** The 3 lowest-scoring clips are identified, and one is chosen randomly from those 3. This prevents the same cortina from playing every time while still ensuring reasonable quality.

**Exclude list:** Already-used filenames are excluded before scoring so the same cortina doesn't repeat back-to-back across tandas. If `exclude` removes all candidates, the full pool is reset and selection proceeds from scratch.

**Returns** the same playlist-ready dict shape as `generator.py`:
```python
{
    "type": "cortina",
    "title": "blue_bossa_30s",
    "file_path": "/path/to/data/cortinas/blue_bossa_30s.mp3",
    "duration": "0:30",
    "source": "pool",
}
```

If the pool itself is empty, a silent placeholder dict is returned.

---

## UI Integration — `page_main.py`

The Streamlit DJ Console calls the cortina subsystem in a three-tier waterfall every time a tanda finishes:

```python
# Tier 1 — Try Lyria generation
if gemini_api_key and tanda_tracks:
    from atdj.cortina.generator import generate_cortina
    cortina = generate_cortina(prev_tracks=tanda_tracks, next_style=next_style,
                               output_dir=ROOT_DIR / "data" / "cortinas" / "generated",
                               api_key=gemini_api_key)
    # → notification: "🎵 CORTINA — Generated via Lyria (Cortina (tango → vals))"

# Tier 2 — Pool fallback
from atdj.cortina.pool import find_best_cortina
cortina = find_best_cortina(_summarize_tanda(tanda_tracks))
# → notification: "🎵 CORTINA — Selected from pool (blue_bossa_30s)"

# Tier 3 — Silent placeholder
cortina = {"type": "cortina", "title": "Cortina", "duration": "0:20", "source": "agent"}
# → warning: "🎵 CORTINA — Pool empty, using placeholder. Add mp3s to data/cortinas/pool/."
```

Cortinas appear in the DJ Console queue with a distinct visual style — dashed border, grey text, `CORTINA` badge — visually separating them from tanda entries so the DJ can see the tanda/cortina/tanda structure at a glance.

### Agent State Connection
The LangGraph `AgentState` carries two cortina-related fields:
- `needs_cortina: bool` — set `True` by `tanda_planner` after a successful tanda, cleared by `cortina_selector`
- `selected_cortina: dict | None` — the chosen cortina dict, passed to `queue_publisher`

The graph router checks `needs_cortina` as a conditional edge: if `True`, the next node is `cortina_selector`; otherwise the graph loops back to `tanda_planner` or routes to `session_summary`.

---

## Data Layout

```
data/
└── cortinas/
    ├── pool_features.csv          # Auto-generated; BPM + energy for each pool clip
    ├── blue_bossa_30s.mp3         # Example pool clip (non-tango, pre-licensed)
    ├── funky_interlude.mp3        # ...add more clips here
    └── generated/                 # Lyria-generated clips saved here at runtime
        ├── cortina_a3f1bc2d.wav
        └── cortina_7e92f4a1.wav
```

**Adding pool clips:** Drop any non-tango `.mp3` or `.wav` files into `data/cortinas/`. Delete `pool_features.csv` (or call `build_pool_features(force=True)`) and it will be rebuilt automatically on the next session start.

---

## Setup

No separate ingest step is needed. The pool is ready as soon as audio files are in `data/cortinas/`. `pool_features.csv` is built on first use.

For Lyria generation, a Gemini API key is required:
```
GOOGLE_API_KEY=...   # in .env, or entered via the Settings page in the UI
```

---

## Design Decisions

**Why Lyria as primary?** A freshly generated cortina is unique to each transition — it can be tailored in BPM, energy, and genre to the specific tanda that just played, producing a more coherent musical arc than any fixed pool clip. This is the generative GenAI capability of the project.

**Why a pool fallback?** Lyria requires a Gemini API key and network access. The pool ensures the session can run offline or under API budget constraints without dead air or structural violations.

**Why randomize from top-3 pool candidates, not always pick the best?** Always picking the lowest-score clip would play the same cortina repeatedly on a long set where the tanda energy profile is similar. Randomizing within the top 3 provides variety while keeping quality high.

**Why 70/30 BPM/energy weighting in pool scoring?** Tempo is the most physically salient feature during a floor transition. Dancers feel a BPM mismatch more acutely than an energy mismatch, so BPM proximity is prioritized.

**Why does the LLM write the Lyria prompt rather than using a template?** A template can only produce a fixed set of prompt variations. The LLM generates novel, musically coherent descriptions that vary naturally across tanda moods, energy levels, and styles — producing cortinas that sound meaningfully different each time rather than cycling through a small set of canned prompts.

**Why exclude used filenames from pool selection?** Hearing the same clip twice in the same milonga is noticeable and breaks the sense of a live, curated set. Exclusion is per-session and resets only if the entire pool has been exhausted.
