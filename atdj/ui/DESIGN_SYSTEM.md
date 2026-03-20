# AT-DJ Design System

## Typography

### Typefaces
All text uses the system default sans-serif: `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
No custom fonts are loaded. Streamlit's monospace fallback (`monospace`) is avoided unless showing code.

### Font Sizes — 4 levels only

| Level | Size | Usage |
|-------|------|-------|
| XS    | 10px | Section labels (uppercase), badge text, captions |
| SM    | 12px | Metadata, orchestra/singer/year, secondary info, track durations |
| MD    | 14px | Body text, UI controls (Streamlit default) |
| LG    | 18px | Song title in Now Playing card |

### Font Weights
- **Regular (400)** — body text, secondary metadata
- **Semibold (600)** — card titles, orchestra names, active session labels
- **Bold (700)** — badges, section labels, cortina label

---

## Colors

### Style Colors — Tango vocabulary
Identify the dance style of each piece. Used for left-border accents, style badges, and playlist row tints.

| Style   | Accent    | Light tint (append `22`) | Usage |
|---------|-----------|--------------------------|-------|
| TANGO   | `#1A5294` | `#1A529422`              | Tango pieces — blue |
| VALS    | `#7B2FA0` | `#7B2FA022`              | Vals pieces — purple |
| MILONGA | `#C44040` | `#C4404022`              | Milonga pieces — red |
| CORTINA | `#777777` | n/a                      | Cortina separator label |

Cortina row background: `#F2F2F2`. Cortina border: `#E5E5E5`.

### Source Colors — Who added this item
Identify whether an item was planned by the AI agent or by the human DJ.

| Source | Accent    | Background | Usage |
|--------|-----------|------------|-------|
| Agent  | `#D97706` | `#FEF3C7`  | Agent-planned items — amber/orange |
| Human  | `#16A34A` | `#DCFCE7`  | Human/DJ-added items — green |

### Brand Color
| Name        | Hex       | Usage |
|-------------|-----------|-------|
| Brand       | `#8B1A1A` | Primary interactive elements: progress bar, active session border, primary buttons |
| Brand Light | `#F0E8E8` | Active session card background |

### Neutral Palette
Use as minimally as possible. Prefer semantic or style colors when an item has a known identity.

| Role              | Hex       | Usage |
|-------------------|-----------|-------|
| Background        | `#FFFFFF` | Card and panel backgrounds |
| Background Subtle | `#F8F8F8` | Scroll containers, page backdrop |
| Border            | `#E5E5E5` | Default card and section borders |
| Border Strong     | `#D0D0D0` | Emphasized dividers |
| Text Primary      | `#1A1A1A` | Main readable text |
| Text Secondary    | `#555555` | Orchestra, singer, metadata lines |
| Text Muted        | `#999999` | Captions, durations, labels, muted UI text |

### Semantic Colors — Session Log
| Type   | Accent    | Background | Usage |
|--------|-----------|------------|-------|
| Info   | `#1A6FAD` | `#E8F4FD`  | Agent decision log entries (blue) |
| Change | `#B7770D` | `#FEF9E7`  | Playlist change notifications (amber) |

---

## Component Patterns

### Badges
- **Style badge** (full): `border-radius: 100px`, `padding: 2px 8px`, `font-size: 10px`, `font-weight: 700`, style accent color with 22% opacity background
- **Source badge** (full): same shape, agent amber or human green
- **Compact badge** (playlist rows): `padding: 1px 5px`, same shape, same colors

### Cards
- Border: `1px solid #E5E5E5`
- Left accent border: `3px solid <style-color>` for style-identified cards; `3px solid #8B1A1A` for active session
- Border radius: `6px` (session cards, playlist rows), `8px` (tanda cards)
- Background: `#FFFFFF`

### Playlist Rows
| State    | Left border           | Background     | Title weight |
|----------|-----------------------|----------------|--------------|
| Playing  | `3px solid <style>`   | `<style>22`    | Bold, `#1A1A1A` |
| Upcoming | `2px solid <style>88` | `<style>11`    | Semibold, `#333333` |
| Cortina  | `2px solid #BBBBBB`   | `#F2F2F2`      | Bold, `#555555` |

All rows: `font-size: 12px` for title and metadata, `padding: 5px 8px`.

### Compact Icon Buttons (playlist ↑/↓/✕, session ✎/✕)
- Height: `24px` (playlist), `26px` (session scroll — overrides music-section CSS)
- Border radius: `4px`
- Padding: `0 4px`
- Font size: `11px`

### Transport Buttons (Playback section)
- Height: `36px` for all four (▶, ⏹, ⏮, ⏭)
- Use `use_container_width=True` with equal-width column pairs for uniform sizing
- Primary (▶): brand color `#8B1A1A`
- Secondary (⏹ ⏮ ⏭): Streamlit default secondary

---

## Layout

### Column structure
| Area       | Width     | Behavior |
|------------|-----------|----------|
| Sidebar    | ~296px    | Fixed (Streamlit default) |
| Main (music) | 520px  | Fixed — does not resize with window |
| Agent Chat | flexible  | `flex: 1 1 auto`, `min-width: 260px` |

### Inner column ratios (within 520px main col)
| Row | Ratio | NP≈ | PB≈ | EA≈ |
|-----|-------|-----|-----|-----|
| Row 1 (NP/PB/EA) | `[2, 2, 5]` | 116px | 116px | 289px |
| Row 3 (SM/SL)    | `[4, 5]`    | 231px | — | 289px |

### Vertical rhythm
- Section dividers `_hr()`: `margin: 14px 0 10px`
- Section labels `_lbl()`: `font-size: 10px`, bold, uppercase, `margin: 0 0 4px`
- Column gap in main content rows: `20px` (between NP/PB/EA and between main/agent)
- Column gap in nested button rows: `16px` (Streamlit default)
- Tight gap inside scroll containers: `2px`

---

## Usage Rules

1. **Never introduce a new color** without checking it is one of the above. For unknown items (no style, no source), use neutral `#555555` or `#999999`.
2. **Darken or lighten** an existing color using the `22` or `88` hex-opacity suffix (8-digit hex) before creating a new one.
3. **Tango blue, Vals purple, Milonga red** are reserved exclusively for dance style identification. Do not use `#1A5294` for anything other than TANGO.
4. **Agent orange / Human green** are reserved for source attribution badges. Do not reuse them for session states or other purposes.
5. **Brand maroon `#8B1A1A`** is the single primary interactive color (progress bar, active session, primary button). Keep it rare.
