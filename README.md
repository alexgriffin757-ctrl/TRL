# Restaurant Launch — Call Analyzer

Upload a sales call recording. Get an instant AI breakdown: summary, objections, buying signals, action items, call grade, and coaching notes.

## Setup

1. Get an Anthropic API key at https://console.anthropic.com (costs ~$0.03 per call analyzed)
2. Install Python 3.10+
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
streamlit run app.py
```

5. Enter your API key in the sidebar and upload a call recording.

## Deploy (Streamlit Cloud — free)

1. Push this folder to a GitHub repo
2. Go to https://share.streamlit.io
3. Connect the repo and select `app.py`
4. Add your API key as a Streamlit Secret: `ANTHROPIC_API_KEY = "sk-ant-..."`
5. Share the URL with your team

## Supported Formats

wav, mp3, m4a, ogg, flac, webm — up to ~25 minutes for best results.

## Cost

- Transcription: Free (runs locally via Whisper)
- AI Analysis: ~$0.03 per call (Claude Sonnet via Anthropic API)
- Hosting: Free on Streamlit Cloud
