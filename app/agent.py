import re
import json
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.workflow import Workflow, START
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types
from app.config import config

# ─── MCP Toolset ────────────────────────────────────────────────────────────
# stdio transport — one toolset instance shared across sub-agents
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "app.mcp_server"],
        ),
    )
)

# ─── Sub-agents (no output_schema — tool calling must stay enabled) ──────────

data_collector = LlmAgent(
    name="data_collector",
    model=config.model,
    description="Collects business metrics and file data using MCP database tools.",
    instruction=(
        "You are a Data Collector Agent. Use the query_database and read_business_file "
        "tools to gather the requested business data. Respond with a clear summary of "
        "all data you collected, including the raw numbers and tables."
    ),
    tools=[mcp_toolset],
)

report_generator = LlmAgent(
    name="report_generator",
    model=config.model,
    description="Formats data into visual reports and drafts stakeholder emails.",
    instruction=(
        "You are a Report Generator Agent. Use the generate_chart_data tool to get "
        "ASCII chart visuals. Then produce:\n"
        "1. A formatted markdown report with tables and ASCII charts.\n"
        "2. A professional email body to stakeholders with the report embedded.\n"
        "Respond with ONLY a JSON object (no markdown fences) in this exact format:\n"
        '{"report": "<full report>", "suggested_email_body": "<email body>"}'
    ),
    tools=[mcp_toolset],
)

# ─── Orchestrator (no output_schema — AgentTool calls must stay enabled) ─────

orchestrator = LlmAgent(
    name="orchestrator",
    model=config.model,
    description="Orchestrates data collection and report generation sub-agents.",
    instruction=(
        "You are the ReportGenie Orchestrator. Follow these steps in order:\n"
        "1. Call the data_collector agent with the user's query to get the raw data.\n"
        "2. Pass that raw data to the report_generator agent to get the formatted "
        "report and email draft.\n"
        "3. Output ONLY the JSON that report_generator returned — do not modify it.\n"
        "The JSON must have keys: report, suggested_email_body."
    ),
    tools=[AgentTool(data_collector), AgentTool(report_generator)],
    output_key="orchestrator_result",
)

# ─── Helper ──────────────────────────────────────────────────────────────────

def make_ui_message(text: str) -> Event:
    return Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=text)]
        )
    )

# ─── Workflow nodes ───────────────────────────────────────────────────────────

def security_checkpoint(ctx: Context, node_input) -> Event:
    """PII scrubbing + prompt injection detection + audit log."""
    # Extract plain text from types.Content or str
    if hasattr(node_input, "parts") and node_input.parts:
        query = "".join(p.text for p in node_input.parts if hasattr(p, "text") and p.text)
    elif isinstance(node_input, str):
        query = node_input
    elif isinstance(node_input, dict):
        query = node_input.get("query") or node_input.get("text") or str(node_input)
    else:
        query = str(node_input)

    # PII scrubbing
    sanitized = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "[REDACTED_EMAIL]", query)
    sanitized = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', "[REDACTED_PHONE]", sanitized)
    sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', "[REDACTED_SSN]", sanitized)
    pii_redacted = sanitized != query

    # Prompt injection & domain rules
    injection_keywords = [
        "ignore previous instructions", "system prompt", "override instructions",
        "bypass safeguards", "ignore rules", "you are now a",
    ]
    is_injection = any(kw in query.lower() for kw in injection_keywords)
    domain_violation = any(w in query.lower() for w in ["password", "credential", "secret_key", "api_key"])

    audit = {
        "event": "security_checkpoint",
        "session_id": ctx.session.id,
        "input_query_length": len(query),
        "pii_redacted": pii_redacted,
        "prompt_injection_detected": is_injection,
        "domain_rule_violated": domain_violation,
    }

    if is_injection or domain_violation:
        audit["action"] = "blocked"
        print(json.dumps({"severity": "CRITICAL", "audit": audit}))
        return Event(
            output={"error": "Security check failed. Request contains blocked content."},
            route="security_violation"
        )

    audit["action"] = "allowed"
    print(json.dumps({"severity": "WARNING" if pii_redacted else "INFO", "audit": audit}))
    return Event(output=sanitized, route="ok", state={"sanitized_query": sanitized})


def security_violation_node(node_input: dict):
    yield make_ui_message(
        f"### ⚠️ Security Violation Detected\n\nRequest blocked: *{node_input.get('error')}*"
    )
    yield Event(output=node_input)


def parse_orchestrator_output(ctx: Context, node_input) -> Event:
    """Parse the orchestrator's free-text JSON result from ctx.state."""
    raw = ctx.state.get("orchestrator_result", "") or ""
    try:
        cleaned = str(raw).strip()
        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        data = json.loads(cleaned)
    except Exception:
        # Fallback: treat entire text as the report
        data = {"report": str(raw), "suggested_email_body": str(raw)}
    return Event(output=data, state={"parsed_report": data})


async def hitl_approval_node(ctx: Context, node_input: dict):
    """Human-in-the-loop: pause and ask user to approve before sending."""
    if not ctx.resume_inputs:
        report = node_input.get("report", "")
        email = node_input.get("suggested_email_body", "")
        yield RequestInput(
            interrupt_id="approve_report",
            message=(
                f"### 📊 Draft Report Generated\n\n{report}\n\n"
                f"**Draft Email Body:**\n```\n{email}\n```\n\n"
                "Do you approve sending this report? Reply **yes** to send, **no** to cancel."
            )
        )
        return
    decision = ctx.resume_inputs.get("approve_report", "").strip().lower()
    yield Event(output=node_input, route="approved" if decision == "yes" else "rejected")


def send_email_node(node_input: dict):
    yield make_ui_message(
        f"### ✅ Report Approved & Sent\n\nEmail dispatched to stakeholders!\n\n"
        f"**Content:**\n```\n{node_input.get('suggested_email_body')}\n```"
    )
    yield Event(output={"status": "sent", "report": node_input.get("report")})


def reject_node(node_input: dict):
    yield make_ui_message("### ❌ Report Cancelled\n\nThe draft was rejected and not sent.")
    yield Event(output={"status": "rejected"})


# ─── Workflow graph ───────────────────────────────────────────────────────────

app_workflow = Workflow(
    name="report_genie_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {"ok": orchestrator, "security_violation": security_violation_node}),
        (orchestrator, parse_orchestrator_output),
        (parse_orchestrator_output, hitl_approval_node),
        (hitl_approval_node, {"approved": send_email_node, "rejected": reject_node}),
    ],
)

root_agent = app_workflow

app = App(
    root_agent=root_agent,
    name="app",
)
