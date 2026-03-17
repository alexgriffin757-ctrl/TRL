"""
Restaurant Launch — Call Analysis Tool
Upload a sales call recording. Get an instant AI breakdown:
strategic sales brief, objections, buying signals, action items, call grade, and coaching notes.
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


# ── Analysis prompt (Claude-grade strategic sales brief) ─────────────────────
ANALYSIS_PROMPT = """You are a senior sales strategist and call analyst for The Restaurant Launch, a restaurant service and sales training company. You analyze discovery and sales calls with the strategic depth of a VP of Sales briefing the founder before a closer call.

You are NOT a summarizer. You are a strategist. Your job is to:
- Read between the lines of what the prospect said
- Identify limiting beliefs they hold that suppress their revenue
- Calculate the dollar opportunity from numbers they gave on the call
- Tell the closer exactly what angle will land hardest
- Be brutally honest in your internal assessment — this is a sales war room document, not a customer-facing report

Below is a transcribed sales/outreach call ({duration:.1f} minutes long).

Analyze it and provide EXACTLY the following sections. Study the example below to understand the DEPTH and TONE expected — then match it for the actual transcript.

=== EXAMPLE OF EXCELLENT ANALYSIS (for reference — do NOT copy this content, analyze the ACTUAL transcript below) ===

## Bottom Line
Momed is a well-respected, chef-driven LA restaurant with strong fundamentals and longevity. Their staff is good and seasoned, but it's market softness and untapped structured sales opportunity. He names upselling as something they want help with, but realistically they have a traffic and guest retention issue that they fail to have any solution for — that is what will hit home the most. With no formalized service system in place, even modest refinements in guided selling and consistency could meaningfully increase per-guest revenue and stabilize performance in a tougher LA market.

## Prospect Profile
**Prospect:** Alex (Owner-Operator)
- Has GM and executive chef, but Alex is the guy.
- **Concept:** Fine-casual, chef-driven, single-unit restaurant
- **Status:** 15 years operating | Established brand | Traffic decline last 2 years (mentions this is overall happening in the area, but I had him admit that a Tuesday afternoon at Houstons is packed. He seems to have a limiting belief that a place like his can't accomplish the same performance without billion dollar operations)
- **Seats + Revenue:** ~170 seats | ~$75-80 avg check (dinner) | ~$3M annual revenue | Clear upside to $85-95 avg check
- **FOH Team:** No dedicated trainer | Long-tenured staff | Owner + GM + Executive Chef leadership structure

## Background & Market Context
- **Location:** Atwater Village, Los Angeles
- **Market pressure:** LA traffic softness impacting covers; business down primarily due to reduced traffic, not retention issues.
- **Strong brand positioning:** Chef-driven concept; menu rotates regularly; not static or chain-structured.
- **Low turnover:** Stable team with long tenure; not a staffing crisis environment.

## Current Training & Operations Reality
- **No formal structured sales training:** Daily meetings occur, but no codified sales/service system in place.
- **Organic operations:** Execution based on experience and culture rather than documented SOP refinement.
- **Owner aware of opportunity:** Open to improvement, particularly around upselling and structured service enhancement.

## Key Service & Sales Opportunities
- **Upselling potential:** Incremental $10-15 per guest achievable through: strategic add-ons, dessert attachment, side pairings, additional shared appetizers
- **Check-average upside:** Moving from $75-80 to $85-95 meaningfully impacts a $3M operation.
- **Performance spread exists:** Standard "rockstar vs. average" variance typical of independent restaurants.
- **Traffic strategy lever:** In softer markets, maximizing per-guest revenue becomes critical.

## Revenue Impact Potential
- Even a 10% lift on $3M = ~$300K incremental revenue.
- Upsell + service flow refinement in fine-casual environments historically produces measurable margin gains without labor additions.
- With strong base check averages already, small refinements compound quickly.

=== END OF EXAMPLE ===

Now analyze the ACTUAL transcript below with the same depth, honesty, and strategic thinking. Include ALL of these sections:

## Bottom Line
A strategic 3-5 sentence assessment. What is the restaurant's REAL situation — not what they said, but what's actually going on? What problem do they have that they may not fully recognize? What limiting beliefs did they express? What angle will hit home hardest when positioning our training? Be direct — this is an internal war room document.

## Prospect Profile
**Prospect:** (Name and role)
- Leadership structure and who actually makes decisions
- **Concept:** (type of restaurant, single/multi-unit)
- **Status:** (years operating, brand strength, traffic/revenue trends — note any limiting beliefs about market conditions vs. their own execution)
- **Seats + Revenue:** (seat count | avg check | estimated annual revenue | upside check target — DO THE MATH with numbers they gave you)
- **FOH Team:** (trainer? tenure? staff quality breakdown if mentioned?)

## Background & Market Context
Bullet points: location, market conditions they mentioned, brand positioning, staffing reality.

## Current Training & Operations Reality
Bullet points: formal training in place? SOPs? What have they tried? What's the gap between what they think they're doing and what's actually happening?

## Key Service & Sales Opportunities
Specific upsell and service opportunities with DOLLAR ESTIMATES. Use the numbers from the call. "Incremental $X per guest achievable through [specific tactics]."

## Revenue Impact Potential
2-3 bullets with REAL MATH. "At [X] covers/day and $[Y] avg check, a $[Z] lift = $[total] annually." Use their numbers.

## Key Moments
Bullet list of the most important moments with timestamps [MM:SS]. Focus on moments that reveal pain, limiting beliefs, or buying signals.

## Objections Raised
Every objection or hesitation. Quote their EXACT words. Note whether the objection is real (logistics) or a limiting belief (mindset).

## Buying Signals
Every positive signal. Quote exact words. Note the strength of each signal.

## Action Items
| # | Action | Owner | Deadline |
|---|--------|-------|----------|
(fill in with specific, actionable items)

## Call Grade
Grade: [A/A+/A-/B+/B/B-/C+/C/C-/D/F]
1-2 sentences explaining the grade. Be specific about what earned or lost points.

## Coaching Notes
3 specific, actionable things the caller could do better next time. Reference specific moments from the call. Don't give generic advice — tell them exactly what to say differently and when.

IMPORTANT: Start the Call Grade section with exactly "Grade: X" on its own line.

---

TRANSCRIPT:
{transcript}"""


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

    # ── Step 2: Analyze with Claude ──────────────────────────────────────
    with st.status("Analyzing with AI...", expanded=True) as status:
        try:
            import anthropic

            # API key loaded from Streamlit secrets or environment
            api_key = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
            if not api_key:
                st.error("ANTHROPIC_API_KEY not configured. Contact your administrator.")
                st.stop()

            client = anthropic.Anthropic(api_key=api_key)

            prompt = ANALYSIS_PROMPT.format(
                duration=duration / 60,
                transcript=transcript,
            )

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            analysis = response.content[0].text

            # Extract grade
            grade_match = re.search(r'Grade:\s*([A-F][+-]?)', analysis)
            grade = grade_match.group(1) if grade_match else "?"

            # Extract prospect name from analysis
            prospect_match = re.search(r'\*\*Prospect:\*\*\s*(.+)', analysis)
            prospect_extracted = prospect_match.group(1).strip() if prospect_match else prospect_name or "Unknown"
            # Clean markdown artifacts from name
            prospect_extracted = re.sub(r'[*_]', '', prospect_extracted).strip()

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

    # Downloadable analysis
    st.download_button(
        "📥 Download Analysis",
        analysis,
        f"analysis_{datetime.now().strftime('%Y%m%d')}_{prospect_extracted.replace(' ', '_')}.md",
        "text/markdown"
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
st.caption("Powered by Restaurant Launch · Recordings are not stored")
