import streamlit as st
import os
import asyncio
from dotenv import load_dotenv
import base64
import datetime
import shutil
import tempfile
import actions
from main import MODEL_ID, build_workflow
from agno.run.workflow import WorkflowRunEvent
import nest_asyncio

nest_asyncio.apply()

st.set_page_config(page_title="Meeting Assistant Agent", layout="wide")

load_dotenv()

with open("./assets/nebius.png", "rb") as nebius_file:
    nebius_base64 = base64.b64encode(nebius_file.read()).decode()

with open("./assets/agno.png", "rb") as agno_file:
    agno_base64 = base64.b64encode(agno_file.read()).decode()

# Create title with embedded image
title_html = f"""
<div style="display: flex;  width: 100%; ">
    <h1 style="margin: 0; padding: 0; font-size: 2.5rem; font-weight: bold;">
        <span style="font-size:2.5rem;">📝</span> Meeting Assistant Agent with
        <img src="data:image/png;base64,{agno_base64}" style="height: 80px; vertical-align: middle; bottom: 10px;"/>
    </h1>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)
st.markdown(
    "**Streamline your meetings with AI-powered transcription, task creation, and notifications**"
)

with st.sidebar:
    st.image("./assets/nebius.png", width=150)
    st.caption(
        "Keys stay in your browser session only. Nebius is required; "
        "Slack and Linear are optional."
    )
    nebius_key = st.text_input(
        "Enter your Nebius API key",
        value=os.getenv("NEBIUS_API_KEY", ""),
        type="password",
    )

    slack_key = st.text_input(
        "Enter your Slack Bot Token (optional)",
        value=os.getenv("SLACK_BOT_TOKEN", ""),
        type="password",
    )

    linear_key = st.text_input(
        "Enter your Linear API key (optional)",
        value=os.getenv("LINEAR_API_KEY", ""),
        type="password",
    )

    uploaded_file = st.file_uploader(
        "Upload Meeting Notes", accept_multiple_files=False, type=["txt"]
    )
    use_sample = st.checkbox(
        "Use the sample meeting notes", value=uploaded_file is None
    )
    with open("./meeting_notes.txt") as sample_file:
        with st.expander("Preview sample notes"):
            st.text(sample_file.read())

    meet_processing = st.button("Process Meeting Notes")

    st.markdown("---")
    st.markdown(
        "Developed with ❤️ by [Arindam Majumder](https://www.youtube.com/c/Arindam_1729)"
    )

about_md = """
## About

This application is powered by a set of advanced AI agents for meeting assistance:

- **Meeting Transcription**: Transcribes meeting notes into a clean summary.
- **Task Creation**: Generates actionable tasks in Linear based on meeting discussions.
- **Slack Notifications**: Sends summaries and key decisions to your Slack channel.

Each stage leverages state-of-the-art language models and tools to enhance productivity and communication.

"""

summary = None
checked_items = None


async def stream_meeting_summary(workflow, file_name, status):
    response = workflow.arun(
        input=f"Process the meeting notes from {file_name}: summarize, create Linear tasks, and send a Slack notification with key outcomes.",
        stream=True,
        stream_events=True,
    )

    content = ""
    async for event in response:
        if event.event == "StepStarted":
            status.update(label=f"🚀 Step started: {event.step_name}")
        elif event.event == "StepCompleted":
            status.update(label=f"✅ Step completed: {event.step_name}")
        elif event.event == "ParallelExecutionStarted":
            status.update(label=f"🔄 Parallel execution started: {event.step_name}")
        elif event.event == "ParallelExecutionCompleted":
            status.update(label=f"✅ Parallel execution completed: {event.step_name}")
        elif event.event in ("RunError", "StepError", "WorkflowError"):
            detail = getattr(event, "error", None) or getattr(event, "content", None)
            raise RuntimeError(
                f"{detail or 'the agent run failed'}. Check that your API keys are valid."
            )
        elif event.event == WorkflowRunEvent.workflow_completed.value:
            content = event.content
    return content


if meet_processing:
    if not nebius_key:
        st.warning("Please enter your Nebius API key in the sidebar.")
    elif not (uploaded_file or use_sample):
        st.warning("Please upload meeting notes or use the sample notes.")
    else:
        # Each run gets its own folder so visitors never see each other's files.
        work_dir = tempfile.mkdtemp(prefix="meeting-")
        failed = False
        try:
            file_name = "meeting_notes.txt"
            if uploaded_file and not use_sample:
                with open(os.path.join(work_dir, file_name), "wb") as f:
                    f.write(uploaded_file.getbuffer())
            else:
                shutil.copy("./meeting_notes.txt", os.path.join(work_dir, file_name))
            with open(os.path.join(work_dir, file_name)) as notes_file:
                notes_text = notes_file.read()
            try:
                # The checked path: action items as validated data, deadlines worked out in code.
                checked_items = actions.extract(
                    notes_text,
                    datetime.date.today(),
                    actions.ChatModel(MODEL_ID, "https://api.studio.nebius.com/v1", nebius_key),
                )
            except Exception:
                checked_items = None  # the summary below still runs
            workflow = build_workflow(
                nebius_key, slack_key or None, linear_key or None, work_dir
            )
            with st.status("Processing meeting notes...", expanded=True) as status:
                summary = asyncio.run(
                    stream_meeting_summary(workflow, file_name, status)
                )
                status.update(label="Processing complete!", state="complete")
        except Exception as e:
            failed = True
            st.error(f"Something went wrong: {e}")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
        if summary:
            if checked_items:
                st.subheader("Action items (validated)")
                st.markdown(actions.as_markdown(checked_items))
            st.markdown(summary)
        elif not failed:
            st.error(
                "The agent didn't return a summary. Check that your Nebius API key is valid."
            )

if not summary:
    st.markdown(about_md)
