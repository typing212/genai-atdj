# Schema Design — AT-DJ

All schemas live in `atdj/schemas/` and are built with **Pydantic v2**. They act as shared data contracts across all modules (audio extraction, agent planner, UI, RAG). Any module that creates or receives structured data must use these models — this prevents integration bugs and ensures type safety without extra validation code.

---

## track.py — `Track`, `TangoStyle`, `AudioQuality`

**What it represents:** A single audio file (tango, vals, milonga, or cortina) in the music pool.

### Enums

| Enum | Values | Purpose |
|---|---|---|
| `TangoStyle` | `tango`, `vals`, `milonga`, `cortina` | Dance style or clip type |
| `AudioQuality` | `raw`, `enhanced` | Whether the file has been denoised |

### Track fields

| Field | Type | Constraint | Source |
|---|---|---|---|
| `id` | str | required | assigned at ingest |
| `title` | str | required | ID3 tag |
| `orchestra` | str | required | ID3 tag |
| `singer` | str or None | optional | ID3 tag |
| `style` | TangoStyle | required | inferred from filename/tag |
| `year` | int | no range constraint | ID3 tag |
| `decade` | int | auto-derived from year | `field_validator` |
| `duration_seconds` | float | > 0 | mutagen |
| `file_path` | str | required | routing logic |
| `audio_quality` | AudioQuality | default `raw` | set after enhancement |
| `enhanced_file_path` | str or None | optional | set after enhancement |
| `bpm` | float or None | optional | librosa |
| `key` | str or None | optional | librosa |
| `energy` | float or None | optional | librosa |
| `danceability` | float or None | optional | librosa |
| `brightness` | float or None | optional | librosa |
| `snr_estimate_db` | float or None | optional | audio analysis |
| `embedding_id` | str or None | optional | ChromaDB |
| `tags` | list[str] | default `[]` | user/agent |
| `notes` | str or None | optional | user/agent |

**Key behavior:** `decade` is always derived automatically from `year` via `field_validator` — you never need to pass it explicitly. Setting `model_config = {"use_enum_values": True}` stores enum values as plain strings (`"tango"` not `TangoStyle.TANGO`), which makes CSV/JSON serialization straightforward.

---

## tanda.py — `Tanda`

**What it represents:** A group of 3–4 tracks played together without interruption, sharing the same orchestra, style, and era.

### Fields

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | str | required | |
| `tracks` | list[Track] | 3–4 items | enforced by `min_length`/`max_length` |
| `style` | TangoStyle | required | must match all tracks |
| `orchestra` | str | required | must match all tracks |
| `era_decade` | int | required | e.g. 1940 |
| `total_duration_seconds` | float | auto-computed | sum of track durations |
| `energy_level` | float | 0.0–1.0 | agent-assigned |
| `position_in_session` | int or None | optional | set during planning |
| `generated_by` | str | default `"agent"` | audit trail |
| `rationale` | str or None | optional | agent explanation |

**Key behavior:** `model_validator(mode="after")` enforces **style homogeneity only** — all tracks must share one style (tango/vals/milonga/cortina). `total_duration_seconds` is also computed here. Orchestra, singer, and decade homogeneity are **soft rules** enforced by the planner layer (`atdj/planner/tanda_rules.py`, WP-05) — they are not validated here so mixed-orchestra or cross-decade tandas can be created when the agent justifies them.

---

## session.py — `Cortina`, `QueueItem`, `MilongaSession`

**What it represents:** The live playback state of an entire milonga evening.

### Cortina

Short music clip (10–35 seconds) played between tandas to signal a partner change.

| Field | Type | Constraint |
|---|---|---|
| `id` | str | required |
| `file_path` | str | required |
| `duration_seconds` | float | 10.0–35.0 seconds |
| `source` | str | origin label |
| `preceding_tanda_id` | str or None | which tanda it follows |
| `features` | dict[str, float] | acoustic features |

### QueueItem

One slot in the session playlist — either a Tanda or a Cortina.

| Field | Type | Notes |
|---|---|---|
| `item_type` | str | `"tanda"` or `"cortina"` |
| `content` | Tanda or Cortina | Union type |
| `scheduled_position` | int | slot index |
| `played` | bool | default False |
| `played_at` | datetime or None | set when played |

### MilongaSession

The top-level session object holding all planning state.

| Field | Default | Notes |
|---|---|---|
| `target_duration_minutes` | 180 | 60–300 min allowed |
| `styles_ratio` | `{tango:0.70, vals:0.20, milonga:0.10}` | DJ preference |
| `avoid_repeat_orchestra_within` | 3 | tanda spacing rule |
| `energy_arc` | `[]` | planned energy curve |
| `actual_energies` | `[]` | recorded as session runs |

---

## feedback.py — `FeedbackEvent`

**What it represents:** A real-time signal from a human operator (DJ, host, or organizer) during the milonga that the agent should act on.

### Fields

| Field | Type | Notes |
|---|---|---|
| `id` | str | required |
| `session_id` | str | links to MilongaSession |
| `timestamp` | datetime | when the event occurred |
| `event_type` | Literal (see below) | strictly enumerated |
| `payload` | dict | optional extra data |
| `processed` | bool | default False; agent sets True after acting |
| `agent_response` | str or None | what the agent did |

### Allowed event_type values

| Value | Meaning |
|---|---|
| `energy_up` | Floor is warming up — increase energy |
| `energy_down` | Floor tiring — decrease energy |
| `skip_tanda` | Skip the current tanda |
| `repeat_orchestra` | Play this orchestra again soon |
| `avoid_orchestra` | Do not schedule this orchestra again |
| `floor_full` | Peak crowd — maintain high energy |
| `floor_empty` | Crowd thinning — wind down |
| `qa_query` | DJ asked a question about tango history/style |
| `manual_override` | DJ manually changed something |

**Key behavior:** `event_type` uses `Literal[...]` — any string not in this list raises a `ValidationError` immediately. `processed` defaults to `False` and is flipped by the agent after it handles the event.

---

## Import map

```
atdj/schemas/
├── track.py        → Track, TangoStyle, AudioQuality
├── tanda.py        → Tanda           (imports Track, TangoStyle)
├── session.py      → Cortina, QueueItem, MilongaSession  (imports Tanda)
└── feedback.py     → FeedbackEvent
```

All four files are re-exported from `atdj/schemas/__init__.py` so other modules can do:
```python
from atdj.schemas import Track, Tanda, MilongaSession, FeedbackEvent
```
