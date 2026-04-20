"""Custom HTML5 audio player with autoplay and auto-advance via JS."""

import base64

import streamlit.components.v1 as components


def render_audio_player(
    file_path: str,
    gap_seconds: float = 0.0,
    max_duration: float | None = None,
    fade_in_seconds: float = 2.0,
) -> None:
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
    b64 = base64.b64encode(audio_bytes).decode()

    max_dur_js = f"{max_duration}" if max_duration else "null"
    gap_ms = int(gap_seconds * 1000)

    html = f"""
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      #atdj-player {{ width:100%; height:40px; }}
    </style>
    <audio id="atdj-player" controls autoplay
           src="data:audio/mp3;base64,{b64}">
    </audio>
    <script>
    const audio = document.getElementById('atdj-player');
    const maxDur = {max_dur_js};
    const fadeIn = {fade_in_seconds};
    const gapMs = {gap_ms};

    // Invalidate any pending auto-skip — a real track is playing
    window.parent.__atdjAutoSkipNonce = null;
    if (window.parent.__atdjAutoSkipTimer) {{ window.parent.clearTimeout(window.parent.__atdjAutoSkipTimer); window.parent.__atdjAutoSkipTimer = null; }}
    window.parent.__atdjGapSignal = null;

    if (fadeIn > 0) {{
        audio.volume = 0;
        const step = 0.05;
        const interval = (fadeIn * 1000) * step;
        const fadeTimer = setInterval(() => {{
            if (audio.volume < 1 - step) {{
                audio.volume = Math.min(1, audio.volume + step);
            }} else {{
                audio.volume = 1;
                clearInterval(fadeTimer);
            }}
        }}, interval);
    }}

    function clickSkip() {{
        const btns = window.parent.document.querySelectorAll('button');
        for (const btn of btns) {{
            if (btn.innerText.includes('\u23ed')) {{ btn.click(); break; }}
        }}
    }}

    function advance() {{
        const advNonce = Math.random().toString(36);
        window.parent.__atdjAutoSkipNonce = advNonce;
        if (window.parent.__atdjAutoSkipTimer) window.parent.clearTimeout(window.parent.__atdjAutoSkipTimer);
        if (gapMs > 0) {{
            window.parent.__atdjGapSignal = {{duration: gapMs, id: advNonce}};
            window.parent.__atdjAutoSkipTimer = window.parent.setTimeout(() => {{
                if (window.parent.__atdjAutoSkipNonce !== advNonce) return;
                clickSkip();
            }}, gapMs);
        }} else {{
            clickSkip();
        }}
    }}

    if (maxDur) {{
        audio.addEventListener('timeupdate', () => {{
            const remaining = maxDur - audio.currentTime;
            if (remaining <= 2 && remaining > 0) {{
                audio.volume = Math.max(0, remaining / 2);
            }}
            if (audio.currentTime >= maxDur) {{
                audio.pause();
                audio.removeAttribute('src');
                advance();
            }}
        }});
    }}

    audio.onended = () => {{ advance(); }};
    </script>
    """
    components.html(html, height=42)
