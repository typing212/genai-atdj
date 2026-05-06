"""Custom HTML5 audio player with autoplay and auto-advance via JS."""

import base64

import streamlit.components.v1 as components


def render_audio_player(
    file_path: str,
    gap_seconds: float = 0.0,
    max_duration: float | None = None,
    fade_in_seconds: float = 2.0,
    autoplay: bool = True,
    is_last_track: bool = False,
) -> None:
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
    b64 = base64.b64encode(audio_bytes).decode()

    max_dur_js = f"{max_duration}" if max_duration else "null"
    gap_ms = int(gap_seconds * 1000)
    # When the last track in the playlist ends, NEVER auto-advance: the
    # ⏭ click would rerun Streamlit, which can interrupt an in-flight agent
    # task (e.g. the user kicked off PLAN/Q&A right before the last track
    # finished). With is_last_track=True the audio just stops at the end —
    # the user can manually advance later if they add more content.
    is_last_js = "true" if is_last_track else "false"
    # 2026-05-01 (Test 7.9): autoplay is now opt-in. Caller passes False on the
    # first iframe render after a fresh PLAN so the user must click ▶ to start.
    # Once they do, the page rerun sets the session flag → caller passes True →
    # subsequent track-to-track auto-advances are seamless.
    autoplay_attr = "autoplay" if autoplay else ""

    html = f"""
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      #atdj-player {{ width:100%; height:40px; }}
    </style>
    <audio id="atdj-player" controls {autoplay_attr}
           src="data:audio/mp3;base64,{b64}">
    </audio>
    <script>
    const audio = document.getElementById('atdj-player');
    // 2026-05-01: maxDur and gapMs were previously baked here as constants,
    // but the Transition / Cortina sliders live in a @st.fragment that does
    // NOT re-render the audio iframe (so audio keeps playing across slider
    // changes). Result: baked values would never update. Fix: read the
    // LATEST value from window.parent at the moment we need it; the slider
    // fragment writes those values via a tiny invisible component on every
    // fragment render. Baked values remain as fallback.
    const bakedMaxDur = {max_dur_js};
    const bakedGapMs = {gap_ms};
    const fadeIn = {fade_in_seconds};
    const isLastTrack = {is_last_js};

    function _readTopVar(name) {{
        // Try window.top first (Streamlit may nest iframes), fall back to window.parent.
        try {{ const v = window.top[name]; if (typeof v === 'number') return v; }} catch (e) {{}}
        try {{ const v = window.parent[name]; if (typeof v === 'number') return v; }} catch (e) {{}}
        return null;
    }}

    function currentGapMs() {{
        const v = _readTopVar('__atdjGapMs');
        return (v !== null && v >= 0) ? v : bakedGapMs;
    }}

    function currentMaxDur() {{
        if (bakedMaxDur === null) return null;  // not a cortina iframe
        const v = _readTopVar('__atdjCortinaSec');
        return (v !== null && v > 0) ? v : bakedMaxDur;
    }}

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
        const gapMs = currentGapMs();
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

    if (bakedMaxDur !== null) {{
        audio.addEventListener('timeupdate', () => {{
            const maxDur = currentMaxDur();
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

    audio.onended = () => {{
        // If this is the last track in the playlist, do NOT auto-advance.
        // The ⏭ click would trigger a Streamlit rerun, which can interrupt
        // an in-flight agent task (a fresh PLAN/Q&A request).
        if (isLastTrack) {{ return; }}
        advance();
    }};

    // Allow the parent window (or harness) to pause this iframe's audio
    // via postMessage. Used by the demo harness to silence music after
    // pre-warm without clearing the playlist (cross-origin iframes block
    // direct audio.pause() from the parent).
    window.addEventListener('message', (e) => {{
        if (e.data === 'atdj-pause') {{
            try {{ audio.pause(); audio.currentTime = 0; }} catch (err) {{}}
        }}
    }});
    </script>
    """
    components.html(html, height=42)
