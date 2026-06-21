import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
import vertexai
from google.genai import types

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

app = FastAPI(title="Manager Approval Dashboard")

# Read project and agent runtime ID from environment variables
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
AGENT_RUNTIME_ID = os.environ.get("AGENT_RUNTIME_ID")

# Fallback project/region parsing from AGENT_RUNTIME_ID if needed
REGION = "us-east1"
if AGENT_RUNTIME_ID and "locations/" in AGENT_RUNTIME_ID:
    parts = AGENT_RUNTIME_ID.split("locations/")
    if len(parts) > 1:
        REGION = parts[1].split("/")[0]

if AGENT_RUNTIME_ID and "projects/" in AGENT_RUNTIME_ID:
    parts = AGENT_RUNTIME_ID.split("projects/")
    if len(parts) > 1:
        PROJECT_ID = parts[1].split("/")[0]

AGENT_ENGINE_SHORT_ID = None
if AGENT_RUNTIME_ID:
    AGENT_ENGINE_SHORT_ID = AGENT_RUNTIME_ID.split("/")[-1] if "/" in AGENT_RUNTIME_ID else AGENT_RUNTIME_ID

class ActionRequest(BaseModel):
    approved: bool
    interrupt_id: str

# HTML Dashboard Template
HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manager Approval Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #0b0c15;
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.08);
            --glass-glow: rgba(138, 43, 226, 0.2);
            --primary: #8a2be2;
            --primary-hover: #9d4edd;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.15);
            --danger: #ef4444;
            --danger-glow: rgba(239, 68, 68, 0.15);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            overflow-x: hidden;
            display: flex;
            flex-direction: column;
            position: relative;
        }

        /* Background glow elements */
        .glow-bg-1 {
            position: fixed;
            top: -200px;
            left: -200px;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(138, 43, 226, 0.15) 0%, transparent 70%);
            z-index: -1;
            pointer-events: none;
        }

        .glow-bg-2 {
            position: fixed;
            bottom: -200px;
            right: -200px;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(74, 0, 224, 0.12) 0%, transparent 70%);
            z-index: -1;
            pointer-events: none;
        }

        header {
            padding: 2rem 4rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--glass-border);
            backdrop-filter: blur(12px);
            z-index: 10;
        }

        .header-title h1 {
            font-size: 1.8rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #fff 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-title p {
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-top: 0.2rem;
        }

        .refresh-btn {
            font-family: 'Outfit', sans-serif;
            font-weight: 500;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            color: var(--text-main);
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.3s ease;
        }

        .refresh-btn:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.2);
            box-shadow: 0 0 15px rgba(255, 255, 255, 0.05);
        }

        main {
            flex: 1;
            padding: 3rem 4rem;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }

        .section-header {
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .section-header h2 {
            font-size: 1.4rem;
            font-weight: 600;
            color: var(--text-main);
        }

        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 2rem;
        }

        .glass-card {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            transition: transform 0.3s ease, border-color 0.3s ease;
            display: flex;
            flex-direction: column;
            gap: 1.2rem;
            position: relative;
            overflow: hidden;
        }

        .glass-card:hover {
            transform: translateY(-4px);
            border-color: rgba(138, 43, 226, 0.3);
            box-shadow: 0 12px 40px 0 rgba(138, 43, 226, 0.1);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }

        .session-badge {
            font-family: 'Inter', sans-serif;
            font-size: 0.75rem;
            background: rgba(255, 255, 255, 0.05);
            padding: 0.3rem 0.6rem;
            border-radius: 6px;
            color: var(--text-muted);
            border: 1px solid var(--glass-border);
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .amount-tag {
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--success);
            text-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
        }

        .card-body {
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
        }

        .merchant-name {
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--text-main);
        }

        .purpose-desc {
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            color: var(--text-muted);
            line-height: 1.4;
        }

        .card-actions {
            display: flex;
            gap: 1rem;
            margin-top: 0.5rem;
        }

        .btn {
            flex: 1;
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
            font-size: 0.95rem;
            padding: 0.75rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            outline: none;
        }

        .btn-approve {
            background: var(--success-glow);
            border: 1px solid var(--success);
            color: var(--success);
        }

        .btn-approve:hover {
            background: var(--success);
            color: #fff;
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);
        }

        .btn-reject {
            background: var(--danger-glow);
            border: 1px solid var(--danger);
            color: var(--danger);
        }

        .btn-reject:hover {
            background: var(--danger);
            color: #fff;
            box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
        }

        /* Side sliding modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            z-index: 100;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }

        .modal-overlay.active {
            opacity: 1;
            pointer-events: all;
        }

        .slide-modal {
            position: fixed;
            top: 0;
            right: 0;
            width: 100%;
            max-width: 550px;
            height: 100vh;
            background: #0f101e;
            border-left: 1px solid var(--glass-border);
            box-shadow: -10px 0 40px rgba(0, 0, 0, 0.5);
            z-index: 101;
            transform: translateX(100%);
            transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            flex-direction: column;
        }

        .slide-modal.active {
            transform: translateX(0);
        }

        .modal-header {
            padding: 2rem;
            border-bottom: 1px solid var(--glass-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-header h3 {
            font-size: 1.4rem;
            font-weight: 600;
            background: linear-gradient(135deg, #fff 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .close-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.8rem;
            cursor: pointer;
            transition: color 0.2s;
        }

        .close-btn:hover {
            color: #fff;
        }

        .modal-content {
            flex: 1;
            padding: 2rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .review-status-box {
            padding: 1.2rem;
            border-radius: 12px;
            background: rgba(138, 43, 226, 0.05);
            border: 1px solid rgba(138, 43, 226, 0.2);
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 10px var(--success);
        }

        .review-text {
            font-family: 'Inter', sans-serif;
            font-size: 0.95rem;
            line-height: 1.6;
            color: var(--text-main);
            white-space: pre-wrap;
        }

        /* Empty state styling */
        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 5rem 2rem;
            background: var(--glass-bg);
            border: 1px dashed var(--glass-border);
            border-radius: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1rem;
        }

        .empty-state h3 {
            font-size: 1.4rem;
            color: var(--text-main);
        }

        .empty-state p {
            color: var(--text-muted);
            font-size: 0.95rem;
        }

        /* Loading spinner */
        .spinner {
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-top: 2px solid currentColor;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            animation: spin 0.8s linear infinite;
            display: inline-block;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .hidden {
            display: none !important;
        }
    </style>
</head>
<body>
    <div class="glow-bg-1"></div>
    <div class="glow-bg-2"></div>

    <header>
        <div class="header-title">
            <h1>Expense Manager Dashboard</h1>
            <p>Real-time AI Expense Auditing & Compliance Control</p>
        </div>
        <button class="refresh-btn" onclick="fetchPendingApprovals()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
            Refresh
        </button>
    </header>

    <main>
        <div class="section-header">
            <h2>Pending Approvals</h2>
        </div>

        <div id="pending-container" class="card-grid">
            <!-- Cards will be populated dynamically -->
        </div>
    </main>

    <!-- Side Slide-Out Modal -->
    <div class="modal-overlay" id="modal-overlay" onclick="closeModal()"></div>
    <div class="slide-modal" id="slide-modal">
        <div class="modal-header">
            <h3>Compliance Review Result</h3>
            <button class="close-btn" onclick="closeModal()">&times;</button>
        </div>
        <div class="modal-content">
            <div class="review-status-box">
                <div class="status-indicator" id="status-indicator"></div>
                <div id="review-status-text" style="font-weight: 500;">Approved</div>
            </div>
            <div class="review-text" id="review-text">
                Review output details...
            </div>
        </div>
    </div>

    <script>
        async function fetchPendingApprovals() {
            const container = document.getElementById('pending-container');
            container.innerHTML = `
                <div class="empty-state">
                    <div class="spinner" style="width: 32px; height: 32px; color: var(--primary);"></div>
                    <p>Fetching pending approvals...</p>
                </div>
            `;

            try {
                const response = await fetch('/api/pending');
                const data = await response.json();

                if (!data || data.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <h3>All Caught Up!</h3>
                            <p>No pending expense approvals requiring review.</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = '';
                data.forEach(item => {
                    const amount = item.expense.amount || -1.0;
                    const merchant = item.expense.merchant || 'Unknown';
                    const purpose = item.expense.purpose || 'Unknown';
                    const message = item.message || 'Requires manual review';

                    const card = document.createElement('div');
                    card.className = 'glass-card';
                    card.innerHTML = `
                        <div class="card-header">
                            <span class="session-badge" title="${item.session_id}">Session: ${item.session_id.substring(0, 12)}...</span>
                            <span class="amount-tag">$${parseFloat(amount).toFixed(2)}</span>
                        </div>
                        <div class="card-body">
                            <div class="merchant-name">${merchant}</div>
                            <div class="purpose-desc">${purpose}</div>
                            <div style="font-size: 0.85rem; color: var(--primary); margin-top: 0.5rem; font-style: italic;">
                                ${message}
                            </div>
                        </div>
                        <div class="card-actions" id="actions-${item.session_id}">
                            <button class="btn btn-reject" onclick="handleAction('${item.session_id}', '${item.interrupt_id}', false)">
                                Reject
                            </button>
                            <button class="btn btn-approve" onclick="handleAction('${item.session_id}', '${item.interrupt_id}', true)">
                                Approve
                            </button>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error(err);
                container.innerHTML = `
                    <div class="empty-state" style="border-color: var(--danger);">
                        <h3 style="color: var(--danger);">Failed to load approvals</h3>
                        <p>Error: ${err.message}</p>
                    </div>
                `;
            }
        }

        async function handleAction(sessionId, interruptId, approved) {
            const actionsDiv = document.getElementById(`actions-${sessionId}`);
            // Save original HTML
            const originalHTML = actionsDiv.innerHTML;
            // Show loading spinner
            actionsDiv.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; width: 100%; gap: 0.5rem; color: var(--text-muted);">
                    <div class="spinner"></div>
                    <span>Processing decision...</span>
                </div>
            `;

            try {
                const response = await fetch(`/api/action/${sessionId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        approved: approved,
                        interrupt_id: interruptId
                    })
                });

                const result = await response.json();
                
                if (response.ok) {
                    // Show modal with final compliance review
                    showModal(approved, result.response);
                    // Refresh data
                    fetchPendingApprovals();
                } else {
                    alert(`Failed to submit decision: ${result.detail || 'Unknown error'}`);
                    actionsDiv.innerHTML = originalHTML;
                }
            } catch (err) {
                console.error(err);
                alert(`Error: ${err.message}`);
                actionsDiv.innerHTML = originalHTML;
            }
        }

        function showModal(approved, reviewText) {
            const modal = document.getElementById('slide-modal');
            const overlay = document.getElementById('modal-overlay');
            const statusBox = document.getElementById('status-indicator');
            const statusText = document.getElementById('review-status-text');
            const contentText = document.getElementById('review-text');

            if (approved) {
                statusBox.style.background = 'var(--success)';
                statusBox.style.boxShadow = '0 0 10px var(--success)';
                statusText.innerText = 'Expense Approved';
                statusText.style.color = 'var(--success)';
            } else {
                statusBox.style.background = 'var(--danger)';
                statusBox.style.boxShadow = '0 0 10px var(--danger)';
                statusText.innerText = 'Expense Rejected';
                statusText.style.color = 'var(--danger)';
            }

            contentText.innerText = reviewText;

            modal.classList.add('active');
            overlay.classList.add('active');
        }

        function closeModal() {
            document.getElementById('slide-modal').classList.remove('active');
            document.getElementById('modal-overlay').classList.remove('active');
        }

        // Initial fetch
        fetchPendingApprovals();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return HTMLResponse(content=HTML_CONTENT)

@app.get("/api/pending")
async def get_pending():
    if not PROJECT_ID or not AGENT_RUNTIME_ID:
        raise HTTPException(
            status_code=500, 
            detail="GOOGLE_CLOUD_PROJECT or AGENT_RUNTIME_ID environment variables are not configured."
        )
    
    try:
        session_service = VertexAiSessionService(
            project=PROJECT_ID,
            location=REGION,
            agent_engine_id=AGENT_ENGINE_SHORT_ID
        )
        
        # List all sessions
        list_resp = await session_service.list_sessions(app_name=AGENT_RUNTIME_ID)
        
        pending_list = []
        for s in list_resp.sessions:
            # Fetch the full history for each session
            full_session = await session_service.get_session(
                app_name=AGENT_RUNTIME_ID,
                user_id=s.user_id,
                session_id=s.id
            )
            if not full_session or not full_session.events:
                continue
                
            calls = {}
            responses = set()
            expense_payload = {}
            
            # Find unresolved adk_request_input calls
            for event in full_session.events:
                if event.node_name == "parser_agent" and event.output:
                    expense_payload = event.output
                    
                for call in event.get_function_calls():
                    if call.name == "adk_request_input":
                        calls[call.id] = (call, expense_payload)
                        
                for resp in event.get_function_responses():
                    if resp.name == "adk_request_input":
                        responses.add(resp.id)
            
            for call_id, (call, exp) in calls.items():
                if call_id not in responses:
                    interrupt_id = call.args.get("interrupt_id")
                    message = call.args.get("message")
                    pending_list.append({
                        "session_id": full_session.id,
                        "user_id": full_session.user_id,
                        "interrupt_id": interrupt_id,
                        "message": message,
                        "expense": exp
                    })
                    
        return pending_list
    except Exception as e:
        logger.exception("Error fetching pending approvals")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/action/{session_id}")
async def api_action(session_id: str, req: ActionRequest):
    if not PROJECT_ID or not AGENT_RUNTIME_ID:
        raise HTTPException(
            status_code=500, 
            detail="GOOGLE_CLOUD_PROJECT or AGENT_RUNTIME_ID environment variables are not configured."
        )
        
    try:
        # Initialize vertexai client
        client = vertexai.Client(project=PROJECT_ID, location=REGION)
        agent = client.agent_engines.get(name=AGENT_RUNTIME_ID)
        
        # Prepare the resume payload to avoid duplicate parameters
        message = {
            "role": "user",
            "parts": [
                {
                    "function_response": {
                        "id": req.interrupt_id,
                        "name": "adk_request_input",
                        "response": {
                            "approved": req.approved,
                            "result": "yes" if req.approved else "no"
                        }
                    }
                }
            ]
        }
        
        logger.info(f"Resuming session {session_id} on agent {AGENT_RUNTIME_ID} with user_id='default-user'")
        
        final_text = ""
        # Call async_stream_query setting user_id strictly to "default-user"
        async for event_data in agent.async_stream_query(
            message=message,
            user_id="default-user",
            session_id=session_id
        ):
            if isinstance(event_data, dict):
                content = event_data.get("content")
                if content and "parts" in content:
                    for part in content["parts"]:
                        text = part.get("text")
                        if text:
                            final_text += text
            elif hasattr(event_data, "content") and event_data.content:
                if event_data.content.parts:
                    for part in event_data.content.parts:
                        if hasattr(part, "text") and part.text:
                            final_text += part.text
                            
        return {"status": "success", "response": final_text or "No text response received from the agent."}
    except Exception as e:
        logger.exception("Error resuming session")
        raise HTTPException(status_code=500, detail=str(e))
