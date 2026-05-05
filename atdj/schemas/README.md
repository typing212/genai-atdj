# Schema Design — AT-DJ

All schemas live in `atdj/schemas/` and are built with **Pydantic v2**. They act as shared data contracts across modules (audio extraction, agent planner, UI, RAG). Any module that creates or receives structured data uses these models — this prevents integration bugs without scattering ad-hoc validation through the codebase.

---

## track.py — `Track`, `TangoStyle`, `AudioQuality`

**What it represents:** a single audio file (tango, vals, milonga, or cortina) in the music pool.

### Enums

| Enum | Values | Purpose |
|---|---|---|
| `TangoStyle` | `tango`, `vals`, `milonga`, `cortina` | Dance style or clip type |
| `AudioQuality` | `raw`, `enhanced` | Whether the file has been processed by the enhancement pipeline |

### Track fields

| Field | Type | Constraint | Source |
|---|---|---|---|
| `id` | str | required | assigned at ingest |
| `title` | str | required | ID3 tag |
| `orchestra` | str | required | ID3 tag |
| `singer` | str or None | optional | ID3 tag |
| `style` | TangoStyle | required | inferred from filename / folder / tag |
| `year` | int | required | ID3 tag |
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
| `tags` | list[str] | default `[]` | user / agent |
| `notes` | str or None | optional | user / agent |

**Key behaviour:** `decade` is always derived automatically from `year` via a `field_validator` — callers do not need to pass it explicitly. `model_config = {"use_enum_values": True}` stores enum values as plain strings (`"tango"` rather than `TangoStyle.TANGO`), which keeps CSV and JSON serialization clean.

---

## tanda.py — `Tanda`

**What it represents:** a group of 3–4 tracks played together without interruption. By tango convention these would also share an orchestra, an era, and ideally a singer; the schema enforces only style.

### Fields

| Field | Type | Constraint |
|---|---|---|
| `id` | str | required |
| `tracks` | list[Track] | 3–4 items |
| `style` | TangoStyle | required |
| `orchestra` | str | required |
| `era_decade` | int | required (e.g. 1940) |
| `total_duration_seconds` | float | auto-computed from tracks |
| `energy_level` | float | 0.0–1.0 |
| `position_in_session` | int or None | optional |
| `generated_by` | str | default `"agent"` |
| `rationale` | str or None | optional agent explanation |

**Key behaviour:** the `validate_homogeneity` model validator enforces only **style** homogeneity — every track in the tanda must share one style (no mixing tango with vals, etc.). The same validator computes `total_duration_seconds`. Orchestra, singer, and decade homogeneity are deliberately left as soft rules — the planner layer is the right place to enforce them, and a deferred "convention vs flexible" planning mode (see `doc/future_work.md` §4) would let the agent break those soft rules when it can justify the break.

---

## session.py — `Cortina`, `QueueItem`, `PlanSession`

**What it represents:** the session-level wrappers used during agent planning. `PlanSession` was renamed from the original `MilongaSession` and slimmed down significantly — it no longer carries playback or planning-target state, only an identity for one agent run.

### Cortina

A short music clip played between tandas to signal a partner change.

| Field | Type | Constraint |
|---|---|---|
| `id` | str | required |
| `file_path` | str | required |
| `duration_seconds` | float | 10.0–35.0 seconds |
| `source` | str | origin label |
| `preceding_tanda_id` | str or None | which tanda it follows |
| `features` | dict[str, float] | acoustic features |

### QueueItem

One slot in a session playlist — either a Tanda or a Cortina.

| Field | Type | Notes |
|---|---|---|
| `item_type` | str | `"tanda"` or `"cortina"` |
| `content` | Tanda or Cortina | Union type |
| `scheduled_position` | int | slot index |
| `played` | bool | default False |
| `played_at` | datetime or None | set when played |

### PlanSession

The lightweight session identity attached to a single PLAN chat request as it flows through the LangGraph.

| Field | Type | Notes |
|---|---|---|
| `id` | str | required |
| `name` | str | required (typically derived from the user's PLAN prompt) |

**Key behaviour:** `PlanSession` represents one agent planning run, not the user-facing milonga session shown in the sidebar. The original `MilongaSession` carried playback state (target duration, styles ratio, energy arc, etc.) but those concerns now live elsewhere — the playlist is owned by the playback engine, the energy arc is rendered directly from selected-track energies, and styles ratio was never wired to anything.

---

## feedback.py — `FeedbackEvent`

**What it represents:** a real-time signal from a human operator (DJ, host, organizer) during the milonga that the agent should act on.

### Fields

| Field | Type | Notes |
|---|---|---|
| `id` | str | required |
| `session_id` | str | links to a PlanSession |
| `timestamp` | datetime | when the event occurred |
| `event_type` | Literal (see below) | strictly enumerated |
| `payload` | dict | optional extra data |
| `processed` | bool | default False; agent flips to True after acting |
| `agent_response` | str or None | what the agent did |

### Allowed event_type values

| Value | Meaning |
|---|---|
| `energy_up` | Floor warming up — increase energy |
| `energy_down` | Floor tiring — decrease energy |
| `skip_tanda` | Skip the current tanda |
| `repeat_orchestra` | Play this orchestra again soon |
| `avoid_orchestra` | Do not schedule this orchestra again |
| `floor_full` | Peak crowd — maintain high energy |
| `floor_empty` | Crowd thinning — wind down |
| `qa_query` | DJ asked a question about tango history or style |
| `manual_override` | DJ manually changed something |

**Key behaviour:** `event_type` uses `Literal[...]` — any string outside this list raises a `ValidationError` immediately. Today the schema is wired into the agent graph but no UI surface produces events; see `doc/future_work.md` §2 (Feedback Interrupt) for the v2 roadmap that activates this loop.

---

## Import map

```
atdj/schemas/
├── track.py        → Track, TangoStyle, AudioQuality
├── tanda.py        → Tanda           (imports Track, TangoStyle)
├── session.py      → Cortina, QueueItem, PlanSession  (imports Tanda)
└── feedback.py     → FeedbackEvent
```

`atdj/schemas/__init__.py` is empty — there is no top-level re-export. Import each model from its own module:

```python
from atdj.schemas.track import Track, TangoStyle, AudioQuality
from atdj.schemas.tanda import Tanda
from atdj.schemas.session import PlanSession, Cortina, QueueItem
from atdj.schemas.feedback import FeedbackEvent
```
