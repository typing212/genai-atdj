"""
atdj/cortina/generator.py
-------------------------
Generate cortina audio clips using Gemini (prompt crafting) + Lyria (audio synthesis).

Public API
----------
generate_cortina(prev_tracks, next_style, output_dir, api_key) -> dict
"""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from statistics import mean

from langchain_core.messages import HumanMessage


# ── Feature extraction ────────────────────────────────────────────────────────

def _summarize_tanda(tracks: list[dict]) -> dict:
    # Dominant style (most common across all tracks)
    styles = [t.get("style", "tango") for t in tracks if t.get("style")]
    style = max(set(styles), key=styles.count) if styles else "tango"

    orchestra = tracks[0].get("orchestra", "unknown") if tracks else "unknown"
    decade = tracks[0].get("decade", "1940s") if tracks else "1940s"

    # Average energy and BPM across all tracks
    energies = [t.get("energy") for t in tracks if t.get("energy") is not None]
    avg_energy = mean(energies) if energies else 0.5
    energy_label = "high" if avg_energy > 0.7 else "moderate" if avg_energy > 0.4 else "low"

    bpms = [t.get("bpm") for t in tracks if t.get("bpm") is not None]
    avg_bpm = round(mean(bpms)) if bpms else None

    # Derive mood from style + energy + bpm
    if style == "milonga":
        mood = "playful and festive" if avg_energy > 0.5 else "light and rhythmic"
    elif style == "vals":
        mood = "romantic and flowing" if avg_energy < 0.6 else "elegant and sweeping"
    else:  # tango
        if energy_label == "high":
            mood = "dramatic and intense"
        elif energy_label == "low":
            mood = "melancholic and tender"
        else:
            mood = "expressive and danceable"

    return {
        "style": style,
        "orchestra": orchestra,
        "decade": decade,
        "energy_label": energy_label,
        "avg_bpm": avg_bpm,
        "mood": mood,
    }


# ── Prompt crafting via Gemini ────────────────────────────────────────────────

def _craft_music_prompt(prev: dict, next_style: str | None) -> str:
    from atdj.config import get_ui_llm
    llm = get_ui_llm()

    bpm_line = f"Tanda BPM: ~{prev['avg_bpm']}" if prev.get("avg_bpm") else ""

    if next_style:
        instruction = f"""Write a short music generation prompt (2-3 sentences) for a 25-second cortina transition.

Tanda just played: a {prev['energy_label']}-energy {prev['mood']} {prev['style']} tanda by {prev['orchestra']} ({prev['decade']})
{bpm_line}
Next tanda style: {next_style}

Rules:
- Must sound completely non-tango — choose a different genre entirely (e.g. jazz, soul, bossa nova, funk, pop, ambient electronic)
- NO bandoneon, NO tango rhythm or compás
- Energy level must match the tanda: {prev['energy_label']} energy
- BPM should stay close to the tanda's tempo so the transition feels natural on the dance floor
- Describe the genre, instrumentation, mood, and energy in plain musical terms
- Reply with the prompt only — no markdown, no explanation"""
    else:
        instruction = f"""Write a short music generation prompt (2-3 sentences) for a 25-second cortina.

Tanda just played: a {prev['energy_label']}-energy {prev['mood']} {prev['style']} tanda by {prev['orchestra']} ({prev['decade']})
{bpm_line}

Rules:
- Must sound completely non-tango — choose a different genre entirely (e.g. jazz, soul, bossa nova, funk, pop, ambient electronic)
- NO bandoneon, NO tango rhythm or compás
- Energy level must match the tanda: {prev['energy_label']} energy
- BPM should stay close to the tanda's tempo so the transition feels natural on the dance floor
- Describe the genre, instrumentation, mood, and energy in plain musical terms
- Reply with the prompt only — no markdown, no explanation"""
    response = llm.invoke([HumanMessage(content=instruction)])
    return response.content.strip()


# ── Lyria audio generation ────────────────────────────────────────────────────

def _call_lyria(music_prompt: str, output_path: Path, api_key: str) -> Path:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=music_prompt)])]
    config = types.GenerateContentConfig(response_modalities=["audio"])

    audio_bytes = b""
    mime_type: str | None = None

    for chunk in client.models.generate_content_stream(
        model="lyria-3-clip-preview",
        contents=contents,
        config=config,
    ):
        if not chunk.parts:
            continue
        part = chunk.parts[0]
        if part.inline_data and part.inline_data.data:
            audio_bytes += part.inline_data.data
            if mime_type is None:
                mime_type = part.inline_data.mime_type

    if not audio_bytes:
        raise RuntimeError("Lyria returned no audio data")

    ext = mimetypes.guess_extension(mime_type or "audio/wav") or ".wav"
    final_path = output_path.with_suffix(ext)
    final_path.write_bytes(audio_bytes)
    return final_path


# ── Public: single cortina ────────────────────────────────────────────────────

def generate_cortina(
    prev_tracks: list[dict],
    next_style: str | None,
    output_dir: Path,
    api_key: str,
) -> dict:
    """Generate one cortina after prev_tracks. next_style=None means closing cortina."""
    output_dir.mkdir(parents=True, exist_ok=True)

    prev = _summarize_tanda(prev_tracks)
    music_prompt = _craft_music_prompt(prev, next_style)

    stem = output_dir / f"cortina_{uuid.uuid4().hex[:8]}"
    file_path = _call_lyria(music_prompt, stem, api_key)

    title = (
        f"Cortina ({prev['style']} → {next_style})" if next_style
        else f"Cortina ({prev['style']})"
    )
    return {
        "type": "cortina",
        "title": title,
        "file_path": str(file_path),
        "duration": "0:25",
        "source": "generated",
        "music_prompt": music_prompt,
    }
