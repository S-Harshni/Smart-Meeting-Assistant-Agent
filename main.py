import os
from pathlib import Path
from agno.agent import Agent
from agno.tools.slack import SlackTools
from agno.tools.linear import LinearTools
from agno.tools.file import FileTools
from agno.workflow import Step, Workflow
from agno.workflow.parallel import Parallel
from agno.models.nebius import Nebius
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MODEL_ID = "moonshotai/Kimi-K2-Instruct"


def build_workflow(nebius_api_key, slack_bot_token=None, linear_api_key=None, work_dir="."):
    """Build the meeting workflow for one set of credentials.

    Keys are passed in (not read from os.environ) so each Streamlit session
    uses its own keys. Slack and Linear steps are only added when their keys
    are provided.
    """
    model = Nebius(id=MODEL_ID, api_key=nebius_api_key)
    file_tools = FileTools(base_dir=Path(work_dir))
    notify_steps = []
    mentions = []

    if linear_api_key:
        linear_agent = Agent(
            name="Linear Task Agent",
            model=model,
            tools=[LinearTools(api_key=linear_api_key)],
            instructions=(
                "You are a productivity assistant. "
                "Your job is to create clear, actionable tasks in Linear based on meeting notes or summaries."
                "For each action item, include a concise title, detailed description, assignee, and deadline if specified. "
                "Reference specific decisions and responsibilities from the meeting notes. "
                "If priorities or deadlines are mentioned, include them."
            ),
            markdown=True,
        )
        notify_steps.append(Step(name="Linear Task", agent=linear_agent))
        mentions.append("tasks on Linear")

    if slack_bot_token:
        slack_agent = Agent(
            name="Slack Notification Agent",
            tools=[SlackTools(token=slack_bot_token)],
            model=model,
            instructions=(
                "You are a communication assistant. "
                "Send a friendly, informative Slack message to the #agent-chat channel summarizing the meeting outcomes. "
                "Highlight key decisions, assigned tasks (with assignees and deadlines), pricing strategy, "
                "and next steps. Use bullet points for clarity and mention any upcoming meetings or deadlines.\n\n"
                "Example message:\n"
                "Hey team! Here's a quick recap of our key decisions from today's session:"
                "🎯 Key Decisions:"
                "• Pricing set at $10,000.\n"
                "• Build cost approved for $2,000.\n\n"
                "📋 Assigned Tasks:\n"
                "• Set up repo: Assigned to Alice, due by 2025-09-20.\n"
                "• Draft proposal: Assigned to Bob, due by 2025-09-18.\n\n"
                "🚴‍♂️ Next Steps:"
                "\n"
                "• Schedule follow-up meeting.\n"
                "• Finalize requirements with the client."
                "You'll find the tasks in Linear. Let's keep the momentum going! 🚀"
            ),
        )
        notify_steps.append(Step(name="Slack Notification Task", agent=slack_agent))
        mentions.append("a quick summary on Slack")

    meeting_task_agent = Agent(
        name="Meeting Transcription Agent",
        tools=[file_tools],
        model=model,
        instructions=(
            "You are a meeting transcription assistant. Read the meeting notes file named in the request "
            "(only read this file, don't modify it). "
            "Transcribe the provided meeting notes into a clean, readable summary. "
            "Capture all important discussion points, including project goals, cost estimates, product tiers, pricing strategy, technical stack, timeline, "
            "decisions, and assigned tasks with deadlines. Format the summary with clear headings and bullet points for easy reading."
            "Write the summary to the meeting_summary.md file."
        ),
        markdown=True,
    )

    see_also = (
        f"Also mention: You can also see {' and '.join(mentions)}.\n\n" if mentions else ""
    )
    summary_agent = Agent(
        name="Meeting Summary Agent",
        model=model,
        instructions=(
            "You are a summarization assistant. "
            "Generate a concise summary of the meeting, focusing on main topics, decisions, pricing, "
            "assigned tasks, and next steps. Format the summary for easy reading and quick reference.\n\n"
            + see_also
            + "Example summary:\n"
            "# 📋 Meeting Summary\n"
            "## 🎯 Main Topics\n"
            "- Project goals and timeline\n"
            "- Pricing strategy\n"
            "- Technical stack\n\n"
            "## 💡 Decisions\n"
            "| Decision      | Details         |\n"
            "|--------------|-----------------|\n"
            "| Pricing       | $10,000 charge  |\n"
            "| Build Cost    | $2,000          |\n"
            "| Tech Stack    | Python, React   |\n\n"
            "## 📝 Assigned Tasks\n"
            "| Task           | Assignee | Deadline    |\n"
            "|---------------|---------|-------------|\n"
            "| Set up repo    | Alice   | 2025-09-20  |\n"
            "| Draft proposal | Bob     | 2025-09-18  |\n\n"
            "## 🚴‍♂️ Next Steps\n"
            "- Schedule follow-up meeting\n"
            "- Finalize requirements\n"
            "- Confirm pricing with client\n"
        ),
        markdown=True,
    )

    steps = [Step(name="Meeting Transcription Task", agent=meeting_task_agent)]
    if len(notify_steps) > 1:
        steps.append(Parallel(*notify_steps, name="Notification Tasks"))
    else:
        steps.extend(notify_steps)
    steps.append(Step(name="Summary Task", agent=summary_agent))

    return Workflow(name="Enhanced Meeting Assistant Workflow", steps=steps)


if __name__ == "__main__":
    workflow = build_workflow(
        os.getenv("NEBIUS_API_KEY"),
        os.getenv("SLACK_BOT_TOKEN"),
        os.getenv("LINEAR_API_KEY"),
    )
    workflow.print_response(
        "Process the meeting notes in meeting_notes.txt: summarize, create Linear tasks, and send a Slack notification with key outcomes."
    )
