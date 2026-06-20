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

import time

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow.utils._workflow_hitl_utils import (
    REQUEST_INPUT_FUNCTION_CALL_NAME,
    get_request_input_interrupt_ids,
    has_request_input_function_call,
)
from google.genai import types

from app.agent import root_agent


def test_auto_approve_under_100() -> None:
    """Tests that expenses under $100 are automatically approved."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    message = types.Content(
        role="user", parts=[types.Part.from_text(text="lunch at Joe's Grill for $45")]
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="test_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events) > 0

    # Ensure the final output confirms auto-approval
    has_approval_msg = False
    for event in events:
        if event.output and "automatically approved" in str(event.output):
            has_approval_msg = True
            break
    assert has_approval_msg, "Expected auto-approval message in events"


def test_review_and_approve_over_100() -> None:
    """Tests that expenses >= $100 trigger review and can be manually approved."""
    # Sleep to avoid hitting Gemini free tier rate limits (5 RPM)
    time.sleep(15)

    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    # Step 1: Submit high expense, expecting a pause/interrupt
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text="New laptop for $1200 at Apple Store")],
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="test_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )

    interrupt_id = None
    for event in events:
        if has_request_input_function_call(event):
            ids = get_request_input_interrupt_ids(event)
            if ids:
                interrupt_id = ids[0]

    assert interrupt_id is not None, "Expected an interrupt requesting manual approval"

    # Step 2: Resume the workflow with a 'yes' response
    resume_message = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    name=REQUEST_INPUT_FUNCTION_CALL_NAME,
                    id=interrupt_id,
                    response={"result": "yes"},
                )
            )
        ],
    )

    resume_events = list(
        runner.run(
            new_message=resume_message,
            user_id="test_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )

    # Ensure the final output confirms reviewer approval
    has_approved_msg = False
    for event in resume_events:
        if event.output and "approved by the reviewer" in str(event.output):
            has_approved_msg = True
            break
    assert has_approved_msg, "Expected manual approval confirmation message"
