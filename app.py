"""Streamlit front end: paste or upload meeting notes, review the checked action items, see what was sent."""
import asyncio
import datetime as dt
from pathlib import Path

import streamlit as st

import actions
import pipeline
from integrations import Linear, Slack

st.set_page_config(page_title="Meeting Assistant Agent", page_icon="📝", layout="wide")
st.title("Meeting Assistant Agent")
st.caption("Meeting notes in. Checked action items, tasks, a team recap and a summary out.")

with st.sidebar:
    st.header("Model")
    provider = st.selectbox("Provider", list(pipeline.PROVIDERS))
    preset = pipeline.PROVIDERS[provider]
    model = st.text_input("Model", preset["model"])
    api_key = st.text_input("API key", type="password") if preset["needs_key"] else "local"
    st.header("Integrations (optional)")
    st.caption("Leave these empty for a dry run: the app shows what it would create and post.")
    linear_key = st.text_input("Linear API key", type="password")
    slack_token = st.text_input("Slack bot token", type="password")
    slack_channel = st.text_input("Slack channel", "#general")
    st.caption("Keys are held in this browser session only and are never written to disk or logs.")

left, right = st.columns([3, 2])
with left:
    uploaded = st.file_uploader("Meeting notes (.txt)", type=["txt"])
    sample = Path(__file__).with_name("sample_meeting.txt").read_text()
    notes = st.text_area("Notes", uploaded.getvalue().decode("utf-8", "replace") if uploaded else sample, height=320)
with right:
    title = st.text_input("Meeting title", "Weekly product sync")
    meeting_date = st.date_input("Meeting date", dt.date.today(), help='Relative deadlines such as "next Friday" are counted from this date.')
    go = st.button("Process notes", type="primary", use_container_width=True)
    st.markdown(
        "**How it works**\n"
        "1. A language model lists the action items as JSON.\n"
        "2. Code validates them and works out each deadline's date.\n"
        "3. Two agents write the recap and the summary at the same time.\n"
        "4. Code creates the Linear tasks and posts the recap to Slack."
    )

if go:
    if not notes.strip():
        st.warning("Add some meeting notes first.")
    elif preset["needs_key"] and not api_key:
        st.warning(f"Enter an API key for {provider}, or switch to the local provider.")
    else:
        with st.status("Working…", expanded=True) as status:
            try:
                result = asyncio.run(pipeline.run(
                    notes, meeting_date, model, preset["base_url"], api_key or "local", title,
                    Linear(linear_key or None), Slack(slack_token or None, slack_channel), on_step=st.write))
                status.update(label="Done", state="complete")
            except Exception as exc:
                result = None
                status.update(label="Failed", state="error")
                st.error(f"Could not reach the model: {exc}")
        if result:
            for warning in result.warnings:
                st.warning(warning)
            st.subheader(f"Action items ({len(result.items)})")
            st.markdown(actions.as_markdown(result.items) if result.items else "No action items found.")
            a, b = st.columns(2)
            with a:
                st.subheader("Tasks")
                st.dataframe(result.tasks, use_container_width=True, hide_index=True)
                st.subheader("Slack recap" + (" (dry run)" if result.slack.get("status") == "dry run" else ""))
                st.code(result.recap, language=None, wrap_lines=True)
            with b:
                st.subheader("Summary")
                st.markdown(result.summary)
