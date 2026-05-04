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
    style = tracks[0].get("style", "tango") if tracks else "tango"
    orchestra = tracks[0].get("orchestra", "unknown") if tracks else "unknown"
    decade = tracks[0].get("decade", "1940s") if tracks else "1940s"
    energies = [t.get("energy") for t in tracks if t.get("energy") is not None]
    avg_energy = mean(energies) if energies else 0.5
    energy_label = "high" if avg_energy > 0.7 else "moderate" if avg_energy > 0.4 else "low"
    return {
        "style": style,
        "orchestra": orchestra,
        "decade": decade,
        "energy_label": energy_label,
    }


# ── Prompt crafting via Gemini ────────────────────────────────────────────────

def _craft_music_prompt(prev: dict, next_style: str | None) -> str:
    from atdj.config import get_ui_llm
    llm = get_ui_llm()
    if next_style:
        instruction = f"""Write a short music generation prompt (2-3 sentences) for a 25-second cortina transition.

Exiting: a {prev['energy_label']}-energy {prev['style']} tanda by {prev['orchestra']} ({prev['decade']})
Entering: a {next_style} tanda

Rules:
- No bandoneon, no tango rhythm — the cortina must sound clearly non-tango
- Brief, neutral, acts as a musical breath between sets
- Describe instrumentation, mood, and the transition arc in plain musical terms
- Reply with the prompt only — no markdown, no explanation"""
    else:
        instruction = f"""Write a short music generation prompt (2-3 sentences) for a 25-second closing cortina.

Closing: a {prev['energy_label']}-energy {prev['style']} tanda by {prev['orchestra']} ({prev['decade']})

Rules:
- No bandoneon, no tango rhythm — the cortina must sound clearly non-tango
- Should feel like a gentle musical close — signals the end of the set, fades to neutral
- Describe instrumentation and mood in plain musical terms
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
