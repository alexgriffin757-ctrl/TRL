"""
Restaurant Launch — Call Analysis Tool
Upload a sales call recording. Get an instant AI breakdown:
summary, objections, buying signals, action items, call grade, and coaching notes.
"""

import streamlit as st
import tempfile, time, json, csv, io, os, re
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Call Analyzer — Restaurant Launch",
    page_icon="🎙️",
    layout="wide",
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #1a252f; margin-bottom: 0; }
    .sub-header { font-size: 1.1rem; color: #666; margin-top: 0; }
    .grade-box {
        font-size: 3rem; font-weight: 800; text-align: center;
        padding: 20px; border-radius: 12px; margin: 10px 0;
    }
    .grade-A { background: #d4edda; color: #155724; }
    .grade-B { background: #d1ecf1; color: #0c5460; }
    .grade-C { background: #fff3cd; color: #856404; }
    .grade-D { background: #f8d7da; color: #721c24; }
    .grade-F { background: #f8d7da; color: #721c24; }
    .metric-card {
        background: #f8f9fa; border-radius: 8px; padding: 16px;
        text-align: center; border: 1px solid #e9ecef;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #2c3e50; }
    .metric-label { font-size: 0.85rem; color: #888; }
    div[data-testid="stSidebar"] { background: #1a252f; }
    div[data-testid="stSidebar"] .stMarkdown { color: #ccc; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ───────────────────────────────────────────────────────
if "call_log" not in st.session_state:
    st.session_state.call_log = []


# ── Sidebar: Settings + Call Log ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://therestaurantlaunch.com/wp-content/uploads/2024/01/cropped-TRL-Logo-1.png", width=200)
    st.markdown("### Settings")

    rep_name = st.text_input("Your Name", placeholder="e.g. Alex, Brandon, Jess")

    st.markdown("---")
    st.markdown("### Call Log")
    if st.session_state.call_log:
        for i, entry in enumerate(reversed(st.session_state.call_log)):
            grade = entry.get("grade", "?")
            grade_color = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🔴", "F": "🔴"}.get(grade[0] if grade else "?", "⚪")
            st.markdown(f"{grade_color} **{entry.get('prospect', 'Unknown')}** — {grade}")
            st.caption(f"{entry.get('rep', 'Unknown')} · {entry.get('date', '')}")
    else:
        st.caption("No calls analyzed yet.")

    st.markdown("---")
    if st.session_state.call_log:
        log_csv = io.StringIO()
        writer = csv.DictWriter(log_csv, fieldnames=["date", "rep", "prospect", "duration", "grade", "outcome"])
        writer.writeheader()
        for entry in st.session_state.call_log:
            writer.writerow({k: entry.get(k, "") for k in ["date", "rep", "prospect", "duration", "grade", "outcome"]})
        st.download_button("📥 Export Call Log (CSV)", log_csv.getvalue(), "call_log.csv", "text/csv")


# ── Main area ────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">Call Analyzer</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Upload a sales call recording — get an instant AI analysis with coaching notes.</p>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Upload call recording",
    type=["wav", "mp3", "m4a", "ogg", "flac", "webm"],
    help="Supports wav, mp3, m4a, ogg, flac, webm. Max ~25 minutes for best results."
)

prospect_name = st.text_input("Prospect / Restaurant Name (optional)", placeholder="e.g. Mario's Trattoria — Mark")

col1, col2 = st.columns([1, 4])
with col1:
    analyze_btn = st.button("🔍 Analyze Call", type="primary", use_container_width=True)


if analyze_btn and uploaded_file:
    # Save uploaded file to temp
    with tempfile.NamedTemporaryFile(suffix=f".{uploaded_file.name.split('.')[-1]}", delete=False) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)

    # ── Step 1: Transcribe ───────────────────────────────────────────────
    with st.status("Transcribing audio...", expanded=True) as status:
        st.write(f"File: {uploaded_file.name} ({file_size_mb:.1f} MB)")

        try:
            from faster_whisper import WhisperModel

            model_size = "small" if file_size_mb > 10 else "base"
            st.write(f"Loading Whisper ({model_size} model)...")

            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments_raw, info = model.transcribe(
                tmp_path, beam_size=5, language="en",
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
            )

            segments = []
            for seg in segments_raw:
                segments.append({
                    "start": round(seg.start, 1),
                    "end": round(seg.end, 1),
                    "text": seg.text.strip(),
                })

            duration = info.duration
            st.write(f"Duration: {duration/60:.1f} min | {len(segments)} segments")
            status.update(label="Transcription complete", state="complete")

        except Exception as e:
            st.error(f"Transcription failed: {e}")
            st.stop()

    # Format transcript
    transcript_lines = []
    for seg in segments:
        mins = int(seg['start'] // 60)
        secs = int(seg['start'] % 60)
        transcript_lines.append(f"[{mins:02d}:{secs:02d}] {seg['text']}")
    transcript = "\n".join(transcript_lines)

    # ── Step 2: Analyze with Groq (Llama 3.3 70B — free) ────────────────
    with st.status("Analyzing with AI...", expanded=True) as status:
        try:
            from groq import Groq

            # API key loaded from Streamlit secrets or environment
            groq_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
            if not groq_key:
                st.error("GROQ_API_KEY not configured. Add it to .streamlit/secrets.toml or environment variables.")
                st.stop()

            client = Groq(api_key=groq_key)

            prompt = f"""You are a sales call analyst for a restaurant service training company. Below is a transcribed sales/outreach call ({duration/60:.1f} minutes long).

Analyze it and provide EXACTLY the following sections:

## Call Summary
2-3 sentence overview of what happened on this call.

## Prospect Info
- **Name:** (prospect's name if mentioned)
- **Restaurant:** (restaurant name if mentioned)
- **Location:** (city/state if mentioned)
- **Role:** (owner, GM, manager, etc.)
- **Locations:** (number of locations if mentioned)

## Key Moments
Bullet list of the most important moments with timestamps [MM:SS].

## Objections Raised
List every objection or hesitation the prospect expressed. Quote their exact words.

## Buying Signals
List any positive signals — questions about pricing, timeline, next steps. Quote exact words.

## Action Items
| # | Action | Owner | Deadline |
|---|--------|-------|----------|
(fill in the table)

## Call Grade
Grade: [A/A+/A-/B+/B/B-/C+/C/C-/D/F]

1-2 sentences explaining the grade.

## Coaching Notes
3 specific, actionable things the caller could do better next time.

IMPORTANT: Start the Call Grade section with exactly "Grade: X" on its own line.

---

TRANSCRIPT:
{transcript}"""

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2500,
                temperature=0.3,
            )
            analysis = response.choices[0].message.content

            # Extract grade
            grade_match = re.search(r'Grade:\s*([A-F][+-]?)', analysis)
            grade = grade_match.group(1) if grade_match else "?"

            # Extract prospect info
            prospect_match = re.search(r'\*\*Name:\*\*\s*(.+)', analysis)
            prospect_extracted = prospect_match.group(1).strip() if prospect_match else prospect_name or "Unknown"

            status.update(label="Analysis complete", state="complete")

        except Exception as e:
            st.error(f"Analysis failed: {e}")
            st.stop()

    # ── Step 3: Display results ──────────────────────────────────────────
    st.markdown("---")

    # Top metrics row
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        grade_class = f"grade-{grade[0]}" if grade and grade[0] in "ABCDF" else "grade-C"
        st.markdown(f'<div class="grade-box {grade_class}">{grade}</div>', unsafe_allow_html=True)
        st.caption("Call Grade")
    with mcol2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{duration/60:.1f}m</div><div class="metric-label">Duration</div></div>', unsafe_allow_html=True)
    with mcol3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(segments)}</div><div class="metric-label">Segments</div></div>', unsafe_allow_html=True)
    with mcol4:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{prospect_extracted[:20]}</div><div class="metric-label">Prospect</div></div>', unsafe_allow_html=True)

    # Full analysis
    st.markdown("---")
    st.markdown(analysis)

    # Downloadable transcript
    st.markdown("---")
    st.download_button(
        "📥 Download Full Transcript",
        transcript,
        f"transcript_{datetime.now().strftime('%Y%m%d')}_{prospect_extracted.replace(' ', '_')}.txt",
        "text/plain"
    )

    # Add to call log
    st.session_state.call_log.append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rep": rep_name or "Unknown",
        "prospect": prospect_extracted,
        "duration": f"{duration/60:.1f} min",
        "grade": grade,
        "outcome": "Analyzed",
    })

    # Cleanup temp file
    try:
        os.unlink(tmp_path)
    except Exception:
        pass

elif analyze_btn and not uploaded_file:
    st.warning("Please upload a call recording first.")


# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Powered by Restaurant Launch · Free AI analysis · Recordings are not stored")
