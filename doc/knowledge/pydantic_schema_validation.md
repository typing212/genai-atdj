# Pydantic as a Data Schema Validation Layer

## Answer Summary
Pydantic is a Python library that defines data structures with strict type and constraint enforcement — similar to SQL `CREATE TABLE` with `CHECK` constraints, but in Python code. Unlike pandas, which silently accepts bad data, Pydantic rejects invalid values the moment an object is created. In AT-DJ, it is used to define `Track`, `Tanda`, `MilongaSession`, and `FeedbackEvent` as validated data contracts that all modules share.

## Key Takeaways
- `class Track(BaseModel)` is the equivalent of a `CREATE TABLE` statement — it defines field names, types, defaults, and constraints in one place
- `Field(ge=1920)`, `Field(gt=0)` are range constraints equivalent to SQL `CHECK` — Pydantic enforces them at object creation time, not later
- Default values (e.g. `audio_quality = AudioQuality.RAW`) behave like SQL `DEFAULT` — automatically filled if not provided
- `field_validator` is a custom constraint — used in `Track` to auto-derive `decade` from `year` (1942 → 1940), like a SQL computed column
- Unlike pandas, Pydantic **fails loudly and immediately** on bad data — wrong type, out-of-range value, or missing required field all raise a `ValidationError` before any downstream code runs
- `model_config = {"use_enum_values": True}` stores enum members as plain strings (e.g. `"tango"` not `TangoStyle.TANGO`), making serialization to CSV/JSON straightforward
- The test suite in `tests/test_schemas.py` verifies that all constraints fire correctly — it is the data quality check layer for the schema definitions themselves

## Relevance to AT-DJ Paper
The use of Pydantic schemas as a shared data contract across all modules (audio extraction, agent planning, UI, RAG) can be cited in the methodology section as an architectural decision that enforces data integrity and reduces integration bugs — particularly important in a multi-module agentic system where modules pass structured data between each other.
