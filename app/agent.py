# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import google.auth
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.events.request_input import RequestInput
from google.adk.models import Gemini
from google.adk.workflow import START, Edge, Workflow, node
from google.genai import types
from pydantic import BaseModel, Field

# Load local environment variables from .env
load_dotenv()

# Set up Vertex AI environment variables
if "GOOGLE_CLOUD_PROJECT" not in os.environ:
    try:
        _, project_id = google.auth.default()
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id or "project-285f4295-92e7-4bf0-94f"
    except Exception:
        os.environ["GOOGLE_CLOUD_PROJECT"] = "project-285f4295-92e7-4bf0-94f"

os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


class Expense(BaseModel):
    amount: float = Field(description="The numeric amount of the expense in dollars.")
    merchant: str = Field(
        description="The merchant or store where the money was spent."
    )
    purpose: str = Field(description="The purpose or description of the expense.")


# Node 1: Extract structured data from raw user input
parser_agent = LlmAgent(
    name="parser_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an expense extraction assistant. Extract the expense details "
        "(amount, merchant, purpose) from the user's input. The amount must be "
        "a float representing dollars. Do not guess; extract only what is provided."
    ),
    output_schema=Expense,
    output_key="expense",
)


# Node 2: Route the expense based on the amount
@node
def route_expense(node_input: dict) -> Event:
    amount = node_input.get("amount", 0.0)
    if amount < 100.0:
        return Event(output=node_input, actions=EventActions(route="auto_approve"))
    else:
        return Event(output=node_input, actions=EventActions(route="review"))


# Node 3: Automatically approve expenses under $100
@node
def auto_approve(node_input: dict) -> str:
    amount = node_input.get("amount", 0.0)
    merchant = node_input.get("merchant", "Unknown")
    purpose = node_input.get("purpose", "Unknown")
    return f"Expense of ${amount:.2f} at {merchant} for '{purpose}' has been automatically approved."


# Node 4: Flag and request manual review for expenses >= $100
@node(rerun_on_resume=True)
async def review_agent(ctx: Context, node_input: dict):
    if not ctx.resume_inputs:
        yield RequestInput(
            interrupt_id="approve_decision",
            message=(
                f"Expense of ${node_input.get('amount', 0.0):.2f} at {node_input.get('merchant', 'Unknown')} "
                f"for '{node_input.get('purpose', 'Unknown')}' requires approval. Approve? (yes/no)"
            ),
        )
        return

    response_data = ctx.resume_inputs.get("approve_decision", {})
    if isinstance(response_data, dict):
        decision = response_data.get("result", "")
    else:
        decision = str(response_data)

    decision = decision.lower().strip()
    amount = node_input.get("amount", 0.0)
    merchant = node_input.get("merchant", "Unknown")
    purpose = node_input.get("purpose", "Unknown")
    if decision == "yes":
        yield Event(
            output=f"Expense of ${amount:.2f} at {merchant} for '{purpose}' has been approved by the reviewer."
        )
    else:
        yield Event(
            output=f"Expense of ${amount:.2f} at {merchant} for '{purpose}' has been rejected by the reviewer."
        )


# Connect nodes into a graph workflow using Edge objects for conditional routing
root_agent = Workflow(
    name="ambient_expense_agent",
    edges=[
        (START, parser_agent),
        (parser_agent, route_expense),
        Edge(from_node=route_expense, to_node=auto_approve, route="auto_approve"),
        Edge(from_node=route_expense, to_node=review_agent, route="review"),
    ],
)

# App wrapping with ResumabilityConfig enabled for HITL state handling
app = App(
    name="app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
