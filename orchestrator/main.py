#!/usr/bin/env python3
import os
import sys
import asyncio
import httpx
import datetime
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from google import genai
from google.genai import types

# Resolve shared folder and local folder import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.abspath(os.path.join(current_dir, "..")))

from shared.contract import CommandModel, ObservationModel, MailNotificationModel
from shared import routing, mcp_intent, web_intent, planner
from shared.memory import MemoryStore
import mcp_google

def load_env():
    env_path = os.path.join(current_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Strip trailing inline comments safely
                if " #" in line:
                    line = line.split(" #", 1)[0].strip()
                elif "\t#" in line:
                    line = line.split("\t#", 1)[0].strip()
                
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip('"').strip("'")
                    os.environ[key.strip()] = val

load_env()

# Local-first agent memory (BigQuery mirror when GCP_PROJECT_ID is set).
memory = MemoryStore()

# Zero-configuration auto-initialization for Google Workspace Docs/Sheets
def auto_init_google_docs():
    doc_id = os.getenv("GOOGLE_DOC_ID")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    has_doc_placeholder = not doc_id or "placeholder" in doc_id or "target-google" in doc_id
    has_sheet_placeholder = not sheet_id or "placeholder" in sheet_id or "target-google" in sheet_id
    
    if has_doc_placeholder or has_sheet_placeholder:
        print("[Auto-Init] Google Doc/Sheet placeholders detected. Dynamically creating target assets...")
        env_updates = {}
        
        if has_doc_placeholder:
            new_doc = mcp_google.create_google_doc("Doppelgänger OS Research Notes")
            if new_doc:
                os.environ["GOOGLE_DOC_ID"] = new_doc
                env_updates["GOOGLE_DOC_ID"] = new_doc
                
        if has_sheet_placeholder:
            new_sheet = mcp_google.create_google_sheet("Doppelgänger OS Activity Log")
            if new_sheet:
                os.environ["GOOGLE_SHEET_ID"] = new_sheet
                env_updates["GOOGLE_SHEET_ID"] = new_sheet
                
        # Write back to .env if any updates were made
        if env_updates:
            env_path = os.path.join(current_dir, ".env")
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r") as f:
                        lines = f.readlines()
                    
                    new_lines = []
                    for line in lines:
                        updated = False
                        for key, val in env_updates.items():
                            if line.startswith(f"{key}="):
                                new_lines.append(f'{key}="{val}"\n')
                                updated = True
                                break
                        if not updated:
                            new_lines.append(line)
                            
                    with open(env_path, "w") as f:
                        f.writelines(new_lines)
                    print("[Auto-Init] Successfully updated .env with dynamic asset IDs.")
                except Exception as e:
                    print(f"[!] Auto-Init .env update failed: {e}")

# Run dynamic Google Cloud Workspace setup
auto_init_google_docs()

# BigQuery memory write-through & read-local loop functions
def bq_save_memory(memory_type: str, content: str, session_id: str = "doppelganger_session"):
    """Persist a memory locally (always) and mirror to BigQuery when configured."""
    memory.save(memory_type, content, session_id)

def bq_get_memory(memory_type: str, session_id: str = "doppelganger_session") -> List[str]:
    """Recall memories of a given type, most-recent-first (local-first)."""
    return memory.recall_contents(memory_type=memory_type)

app = FastAPI(title="Doppelgänger OS — Orchestrator Backend", version="2.1")

# Event-driven resume primitives for active user loop feedback
resume_event = asyncio.Event()
user_response_value = ""

class AgentState:
    def __init__(self):
        self.status = "idle"         # "idle" | "working" | "waiting_for_user" | "completed"
        self.nudge_message = ""      # Message showing in the SwiftUI Notch UI
        self.logs = []               # Console logs for debugging
        self.current_goal = ""       # Current objective
        self.active_task = None      # Asyncio task reference
        self.step_count = 0

agent_state = AgentState()

class InstructionRequest(BaseModel):
    goal: str

@app.get("/")
async def root():
    return {
        "status": "online",
        "role": "orchestrator",
        "port": 8420,
        "agent_status": agent_state.status
    }

@app.get("/state")
async def get_state():
    return {
        "status": agent_state.status,
        "nudge_message": agent_state.nudge_message,
        "logs": agent_state.logs,
        "step_count": agent_state.step_count
    }

@app.post("/instruction")
async def receive_instruction(request: InstructionRequest, background_tasks: BackgroundTasks):
    global user_response_value
    
    if agent_state.status == "waiting_for_user":
        # User responded to a Notch Pill nudge
        user_response_value = request.goal
        log_message(f"[User Input] Received response from Notch UI: '{user_response_value}'")
        agent_state.status = "working"
        resume_event.set()
        return {"status": "resumed", "value": request.goal}
        
    if agent_state.status == "working":
        raise HTTPException(status_code=400, detail="Agent is already busy executing a task")
        
    agent_state.status = "working"
    agent_state.current_goal = request.goal
    agent_state.logs = []
    agent_state.step_count = 0
    agent_state.nudge_message = ""
    resume_event.clear()
    
    task = asyncio.create_task(run_computer_use_loop(request.goal))
    agent_state.active_task = task
    
    return {"status": "started", "goal": request.goal}

@app.post("/observation")
async def receive_observation(observation: ObservationModel):
    log_message(f"[*] Observation received: state={observation.screen_state}, success={observation.result.get('success')}")
    return {"status": "acknowledged"}

@app.post("/mail")
async def receive_mail_notification(mail: MailNotificationModel):
    log_message(f"[Inbox] New email detected from {mail.latest_sender}: '{mail.latest_subject}'")
    agent_state.nudge_message = f"New Email from {mail.latest_sender}: '{mail.latest_subject}'. Want me to handle it?"
    agent_state.status = "waiting_for_user"
    return {"status": "nudge_triggered"}

def log_message(text: str):
    print(text)
    agent_state.logs.append(text)
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../doppelganger_execution.log")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] {text}\n")
    except Exception as e:
        pass

async def _await_user_reply(prompt_text: str) -> str:
    """
    Park the loop, surface a nudge in the Notch UI, and block until the user
    replies via POST /instruction. Returns the user's reply text.
    """
    global user_response_value
    agent_state.nudge_message = prompt_text
    agent_state.status = "waiting_for_user"
    resume_event.clear()
    await resume_event.wait()
    reply = user_response_value
    agent_state.status = "working"
    agent_state.nudge_message = ""
    return reply


def _draft_email(client, goal: str, recipient_hint: str = "", revision: str = "",
                 memory_context: str = "") -> Dict[str, Any]:
    """Synchronous Gemini call producing a structured {to, subject, body} draft."""
    prompt = mcp_intent.build_email_draft_prompt(goal, recipient_hint, revision, memory_context)
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "to": types.Schema(type=types.Type.STRING, description="Recipient email address"),
                    "subject": types.Schema(type=types.Type.STRING, description="Email subject line"),
                    "body": types.Schema(type=types.Type.STRING, description="Email body text"),
                },
                required=["to", "subject", "body"],
            ),
        ),
    )
    try:
        return json.loads(response.text)
    except Exception:
        return {"to": recipient_hint or "", "subject": "", "body": response.text or ""}


async def _handle_gmail(goal: str, client, extra_context: str = "") -> str:
    """Draft an email, confirm with the user, and only then send (irreversible action)."""
    # Recall a prior recipient preference if we have one.
    recipient_hint = ""
    for pref in bq_get_memory("preference"):
        if "client_details" in pref:
            recipient_hint = pref.replace("client_details:", "").strip()
            break

    memory_context = memory.recall_context(goal)
    if extra_context:
        memory_context = (memory_context + "\n\n" if memory_context else "") + \
            "Context from earlier steps (use this in the email):\n" + extra_context
    revision = ""
    for _ in range(3):  # at most 3 draft/confirm rounds
        draft = await asyncio.to_thread(_draft_email, client, goal, recipient_hint, revision, memory_context)
        to = (draft.get("to") or "").strip()
        subject = draft.get("subject", "")
        body = draft.get("body", "")

        # Need a valid recipient before we can present a sendable draft.
        if "@" not in to:
            reply = await _await_user_reply(
                f"Who should I email? I couldn't find a recipient for: '{goal}'"
            )
            recipient_hint = reply.strip()
            revision = ""
            continue

        preview = (
            f"Draft email\nTo: {to}\nSubject: {subject}\n\n{body}\n\n"
            "Reply 'yes' to send, 'no' to cancel, or tell me what to change."
        )
        log_message(f"[MCP/Gmail] Presenting draft for confirmation:\n{preview}")
        reply = await _await_user_reply(preview)

        # Confirm-before-send: check decline FIRST so 'don't send' is never read as 'send'.
        if mcp_intent.is_negative(reply):
            log_message("[MCP/Gmail] User cancelled. Email NOT sent.")
            return f"Email to {to} cancelled by user."
        if mcp_intent.is_affirmative(reply):
            ok = await asyncio.to_thread(mcp_google.send_gmail_message, to, subject, body)
            if ok:
                log_message(f"[MCP/Gmail] Email sent to {to}.")
                bq_save_memory("preference", f"client_details: {to}")
                bq_save_memory("action_log", f"Sent email to {to} re: '{subject}'.")
                return f"Email sent to {to} (subject: {subject})."
            log_message("[MCP/Gmail] Gmail API send failed; draft saved locally as fallback.")
            return f"Gmail send failed for {to}; draft saved locally."
        # Anything else is treated as a revision instruction.
        revision = reply
        log_message(f"[MCP/Gmail] Revising draft per user instruction: '{revision}'")

    log_message("[MCP/Gmail] Reached max revision rounds without confirmation. Email NOT sent.")
    return "Email not sent (max revision rounds reached)."


async def _handle_calendar(goal: str) -> str:
    """Read-only: fetch upcoming calendar events and report them back."""
    events = await asyncio.to_thread(mcp_google.check_google_calendar, 5)
    summary = mcp_intent.format_calendar_events(events)
    log_message(f"[MCP/Calendar] {summary}")
    agent_state.nudge_message = summary
    bq_save_memory("action_log", f"Checked calendar; {len(events)} upcoming events.")
    return summary


async def _handle_docs(goal: str, client, extra_context: str = "") -> str:
    """Append content to the Doc. If upstream context exists (e.g. a summary), append
    that directly; otherwise generate fresh content from the goal."""
    doc_id = os.getenv("GOOGLE_DOC_ID")
    if extra_context:
        content = extra_context
    else:
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-3-flash-preview',
            contents=mcp_intent.build_doc_content_prompt(goal),
        )
        content = resp.text or ""
    if doc_id:
        ok = await asyncio.to_thread(mcp_google.append_to_google_doc, doc_id, f"\n\n{content}\n")
        log_message("[MCP/Docs] Appended content to Google Doc." if ok else "[MCP/Docs] Doc append failed.")
        result = "Appended content to Google Doc." if ok else "Doc append failed."
    else:
        log_message("[MCP/Docs] No GOOGLE_DOC_ID configured; skipping append.")
        result = "No GOOGLE_DOC_ID configured."
    bq_save_memory("action_log", f"Appended doc content for goal: '{goal}'.")
    return result


async def _handle_sheets(goal: str, extra_context: str = "") -> str:
    """Append a tracking row to the configured Google Sheet."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if sheet_id:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        detail = (extra_context[:120] if extra_context else goal)
        row = [ts, "Manual MCP task", detail, "N/A", "Logged"]
        ok = await asyncio.to_thread(mcp_google.append_to_google_sheet, sheet_id, row)
        log_message("[MCP/Sheets] Appended row to Google Sheet." if ok else "[MCP/Sheets] Sheet append failed.")
        result = "Appended row to Google Sheet." if ok else "Sheet append failed."
    else:
        log_message("[MCP/Sheets] No GOOGLE_SHEET_ID configured; skipping append.")
        result = "No GOOGLE_SHEET_ID configured."
    bq_save_memory("action_log", f"Logged sheet row for goal: '{goal}'.")
    return result


async def web_answer(goal: str, client, agent_server_url: str, extra_context: str = "") -> str:
    """
    General web pipeline core (ROUTING.md Tier 2): resolve the goal to a URL or search,
    extract page text headlessly via Chrome CDP, then have Gemini answer/summarize.
    Returns the answer text (or "" on failure).
    """
    target = web_intent.build_target(goal)
    log_message(f"[Web] Handling web task: '{goal}' -> {target}")

    cmd = CommandModel(path="browser_use", action="extract", args={"url": target})
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.post(
                f"{agent_server_url}/command", json=cmd.model_dump(), timeout=45.0
            )
        except Exception as e:
            log_message(f"[!] Web extract request failed: {e}")
            return ""

    if res.status_code != 200:
        log_message(f"[!] Web extract failed: HTTP {res.status_code}")
        return ""

    result = res.json().get("result", {})
    text = result.get("text", "")
    if not text:
        log_message("[Web] No page text extracted; nothing to summarize.")
        return ""

    log_message(f"[Web] Extracted {len(text)} chars from {result.get('page_url', target)}. Summarizing via Gemini...")
    web_prompt = web_intent.build_web_answer_prompt(goal, text)
    mem_context = memory.recall_context(goal)
    preamble = "\n\n".join(p for p in (mem_context, extra_context) if p)
    if preamble:
        web_prompt = preamble + "\n\n" + web_prompt
    resp = await asyncio.to_thread(
        client.models.generate_content,
        model='gemini-3-flash-preview',
        contents=web_prompt,
    )
    answer = resp.text or ""
    log_message(f"[Web] Answer:\n{answer}")
    bq_save_memory("action_log", f"Web task answered: '{goal}'.")
    return answer


async def handle_web_task(goal: str, client, agent_server_url: str):
    """Single-task entry point: run web_answer and surface the result in the UI."""
    answer = await web_answer(goal, client, agent_server_url)
    if answer:
        agent_state.nudge_message = answer[:400]
    agent_state.status = "completed"


async def handle_mcp_task(goal: str, capability: Optional[str], client):
    """
    Dispatch an API-backed task directly (no visual loop). MCP always wins for
    Docs/Sheets/Gmail/Calendar (see ROUTING.md). Only Gmail requires confirmation.
    """
    log_message(f"[MCP] Handling '{capability}' task via API. Goal: '{goal}'")
    try:
        if capability == "gmail":
            await _handle_gmail(goal, client)
        elif capability == "calendar":
            await _handle_calendar(goal)
        elif capability == "docs":
            await _handle_docs(goal, client)
        elif capability == "sheets":
            await _handle_sheets(goal)
        else:
            log_message(f"[MCP] Unknown capability '{capability}'; nothing to do.")
    except Exception as e:
        log_message(f"[!] MCP task failure: {e}")
    agent_state.status = "completed"


async def reddit_summary(client, agent_server_url: str) -> str:
    """Scrape the ML subreddit (CDP, with HN/cached fallback) and return a summary string.
    Unlike the standalone shortcut, this does NOT write to Docs/Sheets — in a plan those
    are separate steps that consume this summary as context."""
    async with httpx.AsyncClient() as http_client:
        try:
            cmd = CommandModel(path="browser_use", action="read", args={})
            res = await http_client.post(f"{agent_server_url}/command", json=cmd.model_dump(), timeout=30.0)
            posts = res.json().get("result", {}).get("posts", []) if res.status_code == 200 else []
        except Exception as e:
            log_message(f"[Planner] Reddit scrape failed: {e}")
            posts = []
    if not posts:
        return ""
    summary_prompt = (
        "Write a concise, professional digest of these top posts. "
        "Use markdown with bold headings, bullets, and clean URLs:\n\n"
    )
    for idx, p in enumerate(posts, 1):
        summary_prompt += f"{idx}. Title: {p['title']}\n   Link: {p['url']}\n\n"
    resp = await asyncio.to_thread(
        client.models.generate_content, model='gemini-3-flash-preview', contents=summary_prompt
    )
    summary = resp.text or ""
    log_message(f"[Planner] Reddit summary generated ({len(summary)} chars).")
    return summary


async def _desktop_substep_loop(task: str, client, agent_server_url: str, max_steps: int = 8) -> str:
    """Compact visual loop for a desktop sub-task within a plan (computer_use only).
    Requires Profile B foreground; fails closed and nudges otherwise."""
    log_message(f"[Planner/Desktop] Visual sub-task: '{task}'")
    async with httpx.AsyncClient() as http_client:
        for step in range(1, max_steps + 1):
            try:
                status_res = await http_client.get(f"{agent_server_url}/")
                data = status_res.json() if status_res.status_code == 200 else {}
                active = data.get("active_console", False)
            except Exception:
                active = False
            if not active:
                agent_state.nudge_message = "Please fast-user-switch to Profile B for the desktop step!"
                agent_state.status = "waiting_for_user"
                resume_event.clear()
                await resume_event.wait()
                agent_state.nudge_message = ""
                agent_state.status = "working"

            try:
                frame = await http_client.get(f"{agent_server_url}/frame.jpg")
                image_bytes = frame.content
            except Exception as e:
                log_message(f"[Planner/Desktop] Screenshot error: {e}")
                await asyncio.sleep(1)
                continue

            sys_prompt = (
                "You are the visual brain of Doppelgänger OS on a macOS screen (1440x900). "
                f"Complete this sub-task: '{task}'. Output coordinate clicks (0-1440 x 0-900), typing, "
                "keys, or scroll. To LAUNCH an app, click its Dock/Launchpad icon (avoid Spotlight/"
                "command+space — system hotkeys are unreliable in the background). App shortcuts "
                "(command+c/v) work via action='key'. action='type' may include both 'text' and "
                "'key'='enter' to type then submit. When finished, output action='completed'."
            )
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model='gemini-3-flash-preview',
                    contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), sys_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "thought": types.Schema(type=types.Type.STRING),
                                "action": types.Schema(
                                    type=types.Type.STRING,
                                    enum=["click", "type", "key", "scroll", "noop", "completed"],
                                ),
                                "args": types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "x": types.Schema(type=types.Type.INTEGER),
                                        "y": types.Schema(type=types.Type.INTEGER),
                                        "text": types.Schema(type=types.Type.STRING),
                                        "key": types.Schema(type=types.Type.STRING),
                                        "amount": types.Schema(type=types.Type.INTEGER),
                                    },
                                ),
                            },
                            required=["thought", "action"],
                        ),
                    ),
                )
                pred = json.loads(response.text)
            except Exception as e:
                log_message(f"[Planner/Desktop] Brain error: {e}")
                break

            action = pred.get("action", "noop")
            args = pred.get("args", {})
            log_message(f"[Planner/Desktop] {pred.get('thought','')} -> {action} {args}")
            if action == "completed":
                return f"Desktop sub-task done: {task}"

            cmd = CommandModel(path="computer_use", action=action, args=args)
            try:
                cmd_res = await http_client.post(
                    f"{agent_server_url}/command", json=cmd.model_dump(), timeout=15.0
                )
                if cmd_res.status_code == 200 and cmd_res.json().get("screen_state") == "background_lock":
                    log_message("[Planner/Desktop] Background lock; will nudge to switch.")
                    continue
            except Exception as e:
                log_message(f"[Planner/Desktop] Dispatch error: {e}")
            await asyncio.sleep(1.5)
    return f"Desktop sub-task ended (step budget reached): {task}"


async def dispatch_open_app(app: str, agent_server_url: str) -> str:
    """Launch a native app in Profile B via the session-safe open_app action (open -a).
    Runs in B's own session, so it never hijacks Profile A and works regardless of
    foreground state — the reliable alternative to pixel-clicking the Dock."""
    cmd = CommandModel(path="computer_use", action="open_app", args={"name": app})
    result = {}
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.post(f"{agent_server_url}/command", json=cmd.model_dump(), timeout=15.0)
            if res.status_code == 200:
                result = res.json().get("result", {})
        except Exception as e:
            log_message(f"[!] open_app dispatch failed: {e}")
            return ""
    detail = result.get("detail") or result.get("error_message", "")
    if result.get("success"):
        log_message(f"[OpenApp] {detail}")
        bq_save_memory("action_log", f"Opened app: {app}")
        return detail
    log_message(f"[OpenApp] Failed: {detail}")
    return f"Could not open {app}: {detail}"


async def execute_plan_step(task: str, client, agent_server_url: str, context: str) -> str:
    """Route and execute one plan step, returning its textual result for downstream steps."""
    decision = routing.classify_goal(task)
    log_message(f"[Planner] Routing step '{task}' -> {decision.route}/{decision.mcp_capability or '-'}")
    if decision.route == "mcp":
        cap = decision.mcp_capability
        if cap == "gmail":
            return await _handle_gmail(task, client, extra_context=context)
        if cap == "calendar":
            return await _handle_calendar(task)
        if cap == "docs":
            return await _handle_docs(task, client, extra_context=context)
        if cap == "sheets":
            return await _handle_sheets(task, extra_context=context)
        return ""
    if decision.route == "browser":
        if routing.is_reddit_scrape_shortcut(task):
            return await reddit_summary(client, agent_server_url)
        return await web_answer(task, client, agent_server_url, extra_context=context)
    # desktop: prefer the session-safe open_app for app launches; pixels otherwise.
    app = routing.parse_app_launch(task)
    if app:
        return await dispatch_open_app(app, agent_server_url)
    return await _desktop_substep_loop(task, client, agent_server_url)


async def run_task_plan(steps, client, agent_server_url: str):
    """Execute an ordered plan, carrying each step's output forward as shared context."""
    context = ""
    for idx, task in enumerate(steps, 1):
        agent_state.step_count = idx
        log_message(f"[Planner] === Step {idx}/{len(steps)}: {task} ===")
        try:
            out = await execute_plan_step(task, client, agent_server_url, context)
        except Exception as e:
            log_message(f"[!] Plan step {idx} failed: {e}")
            out = ""
        if out:
            context += f"\n\n[Result of step {idx} — {task}]:\n{out}"
            memory.save("action_log", f"Plan step {idx} ({task}) -> {out[:120]}")
    log_message("[Planner] Task plan complete.")
    agent_state.nudge_message = "All steps complete."
    agent_state.status = "completed"


async def plan_tasks(goal: str, client) -> list:
    """Decompose a compound goal into ordered sub-tasks (single-item list if simple)."""
    if not planner.looks_compound(goal):
        return [goal]
    log_message("[Planner] Goal looks compound; decomposing via Gemini...")
    try:
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-3-flash-preview',
            contents=planner.build_plan_prompt(goal),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "steps": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                properties={"task": types.Schema(type=types.Type.STRING)},
                                required=["task"],
                            ),
                        )
                    },
                    required=["steps"],
                ),
            ),
        )
        data = json.loads(resp.text)
        steps = planner.normalize_steps(data.get("steps", []))
        return steps or [goal]
    except Exception as e:
        log_message(f"[Planner] Decomposition failed: {e}. Treating as single task.")
        return [goal]


async def run_computer_use_loop(goal: str):
    """
    Core Gemini Vision-to-Action loop executing on Port 8420.
    Supports BOTH pure Computer Use (Spotlight, Chrome UI visual clicking)
    AND high-performance Browser Use (Playwright remote CDP browser automation).
    """
    log_message(f"[Loop] Initiating hybrid Autonomous loop for goal: '{goal}'")
    memory.save("interaction", f"User goal: {goal}")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        log_message("[!] Error: GOOGLE_API_KEY is missing from .env. Terminating loop.")
        agent_state.status = "idle"
        return
        
    client = genai.Client(api_key=api_key)
    agent_server_url = os.getenv("AGENT_SERVER_URL", "http://127.0.0.1:8421")
    
    # [P2 Stretch] Session Transplant
    if os.getenv("ENABLE_SESSION_TRANSPLANT", "false").lower() == "true":
        log_message("[Session Transplant] Session transplant is active. Initiating cookie transfer from Profile A...")
        try:
            import shared.session_transplant as session_transplant
            cookies = await session_transplant.extract_cookies_from_profile_a(9223)
            if cookies:
                async with httpx.AsyncClient() as http_client:
                    transplant_res = await http_client.post(
                        f"{agent_server_url}/transplant",
                        json={"cookies": cookies},
                        timeout=5.0
                    )
                    if transplant_res.status_code == 200:
                        log_message(f"[Session Transplant] Successfully transplanted {len(cookies)} cookies to Clone browser.")
                    else:
                        log_message(f"[!] Session transplant failed on agent-server: HTTP {transplant_res.status_code}")
            else:
                log_message("[Session Transplant] No cookies extracted. Continuing with default browser session.")
        except Exception as e:
            log_message(f"[!] Session transplant exception: {e}")
    
    # Check BigQuery Memory for active learning prior preference
    log_message("[BigQuery] Checking memory table for prior preferences...")
    prior_prefs = bq_get_memory("preference")
    client_pref = None
    if prior_prefs:
        for pref in prior_prefs:
            if "client_details" in pref:
                client_pref = pref.replace("client_details:", "").strip()
                log_message(f"[BigQuery] Recalled prior preference: '{client_pref}'")
                break
                
    # Compound-task planner (Phase 6): decompose & sequence multi-step goals, carrying
    # each step's output forward as shared context. Single-step goals fall through
    # unchanged to the routing below.
    plan = await plan_tasks(goal, client)
    if len(plan) > 1:
        log_message(f"[Planner] Decomposed into {len(plan)} steps: {plan}")
        await run_task_plan(plan, client, agent_server_url)
        return

    # MCP fast-path (ROUTING.md): API-backed goals (Docs/Sheets/Gmail/Calendar) are
    # handled directly and never touch the visual loop. MCP always wins.
    decision = routing.classify_goal(goal)
    if decision.route == "mcp":
        log_message(f"[Router] Goal routed to MCP/{decision.mcp_capability} ({decision.reason}). Bypassing visual loop.")
        await handle_mcp_task(goal, decision.mcp_capability, client)
        return

    if "email" in goal.lower() or "draft" in goal.lower():
        if not client_pref:
            log_message("[Confidence Gate] Missing client details. Triggering user nudge feedback loop...")
            agent_state.nudge_message = "Need client details (Name/Email) to draft email."
            agent_state.status = "waiting_for_user"
            resume_event.clear()
            
            # Asynchronously block the execution loop until user replies in SwiftUI
            await resume_event.wait()
            
            # Save user reply to BigQuery as preference to complete active learning cycle
            client_pref = user_response_value
            log_message(f"[BigQuery] Saving user response as preference: '{client_pref}'")
            bq_save_memory("preference", f"client_details: {client_pref}")
            agent_state.nudge_message = ""
            
        goal = f"{goal} addressed to client: {client_pref}"
        log_message(f"[Loop] Resuming task with updated goal: '{goal}'")
    
    # Programmatic Scraper Shortcut Pathway (GATE 5 & 6)
    # If the goal is programmatic scraping, bypass the visual desktop screenshot loop 
    # to prevent context confusion from visible HUD logs or instructions on screen.
    is_programmatic = routing.is_reddit_scrape_shortcut(goal)
    if is_programmatic:
        log_message("[Loop] Detected programmatic scraper goal. Executing fast browser scrape directly...")
        async with httpx.AsyncClient() as http_client:
            try:
                # Dispatch browser_use scrape command directly to agent-server
                log_message("[Browser Use] Dispatching r/MachineLearning scraper to agent-server...")
                cmd_payload = CommandModel(
                    path="browser_use",
                    action="read",
                    args={}
                )
                cmd_response = await http_client.post(
                    f"{agent_server_url}/command",
                    json=cmd_payload.model_dump(),
                    timeout=30.0
                )
                
                if cmd_response.status_code != 200:
                    log_message(f"[!] Scraper command failed: HTTP {cmd_response.status_code}")
                else:
                    res_data = cmd_response.json()
                    scrape_result = res_data.get("result", {})
                    posts = scrape_result.get("posts", [])
                    log_message(f"[Browser Use] Scrape successful! Found {len(posts)} posts.")
                    
                    if posts:
                        # 1. Summarize posts
                        summary_prompt = (
                            "Write a beautiful, highly professional and detailed newsletter-style digest summary "
                            "of the following 3 hot Machine Learning posts. Use markdown formatting with clear bold headings, "
                            "bulleted insights, and clean URLs:\n\n"
                        )
                        for idx, p in enumerate(posts, 1):
                            summary_prompt += f"{idx}. Title: {p['title']}\n   Link: {p['url']}\n\n"
                            
                        log_message("[Brain] Summarizing Reddit posts via Gemini...")
                        sum_response = await asyncio.to_thread(
                            client.models.generate_content,
                            model='gemini-3-flash-preview',
                            contents=summary_prompt
                        )
                        summary_text = sum_response.text
                        log_message(f"[Brain] Generated Summary:\n{summary_text}")
                        
                        # 2. Append to Google Doc
                        doc_id = os.getenv("GOOGLE_DOC_ID")
                        if doc_id:
                            log_message(f"[Google Docs] Appending summary to Doc: {doc_id}...")
                            success_doc = mcp_google.append_to_google_doc(doc_id, f"\n\n--- REDDIT MACHINE LEARNING DIGEST ---\n\n{summary_text}")
                            if success_doc:
                                log_message("[Google Docs] Successfully synced to Cloud Document.")
                            else:
                                log_message("[!] Google Docs sync failed.")
                                
                        # 3. Append row to Google Sheet
                        sheet_id = os.getenv("GOOGLE_SHEET_ID")
                        if sheet_id:
                            log_message(f"[Google Sheets] Appending log row to Sheet: {sheet_id}...")
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            doc_link = f"https://docs.google.com/document/d/{doc_id}/edit" if doc_id else "N/A"
                            row_values = [
                                timestamp, 
                                "Machine Learning Subreddit Research", 
                                f"Scraped {len(posts)} posts", 
                                doc_link, 
                                "Completed Successfully"
                            ]
                            success_sheet = mcp_google.append_to_google_sheet(sheet_id, row_values)
                            if success_sheet:
                                log_message("[Google Sheets] Successfully synced log row.")
                            else:
                                log_message("[!] Google Sheets sync failed.")
                                
                        # 4. Save to BigQuery Memory table
                        log_message("[BigQuery] Saving action log to memory table...")
                        bq_save_memory(
                            memory_type="action_log",
                            content=f"Scraped r/MachineLearning. Top post: '{posts[0]['title']}'."
                        )
                        
                log_message("[x] Scraping, summarizing, and Cloud Doc/Sheet writing completed!")
                log_message("[Loop] Completed tasks execution pipeline.")
                agent_state.status = "completed"
                return
            except Exception as e:
                log_message(f"[!] Programmatic scraper failure: {e}")
                log_message("Falling back to visual computer use loop...")

    # General web fast-path (ROUTING.md Tier 2): any web/DOM goal that isn't the
    # specialized Reddit shortcut is answered by extract -> summarize, no visual loop.
    if decision.route == "browser":
        await handle_web_task(goal, client, agent_server_url)
        return

    # Session-safe app launch (open -a in B) — preferred over pixel-clicking the Dock,
    # and never hijacks Profile A. Works regardless of foreground state.
    app = routing.parse_app_launch(goal)
    if decision.route == "desktop" and app:
        log_message(f"[Router] App-launch '{app}' via open_app (session-safe).")
        await dispatch_open_app(app, agent_server_url)
        agent_state.status = "completed"
        return

    loop_memory_context = memory.recall_context(goal)
    max_steps = 15
    async with httpx.AsyncClient() as http_client:
        for step in range(1, max_steps + 1):
            agent_state.step_count = step
            
            # Loop detection confidence gate
            if step > 12:
                log_message("[Confidence Gate] Loop detected! Terminating task to prevent resource exhaustion.")
                break
                
            background_headless_hint = False
            # Safety Check: Proactively verify if Profile B is the active console GUI session
            try:
                status_res = await http_client.get(f"{agent_server_url}/")
                if status_res.status_code == 200:
                    status_data = status_res.json()
                    # FAIL CLOSED: missing/unknown active_console is treated as background
                    # so desktop computer_use is never attempted on an unverified session.
                    if not status_data.get("active_console", False):
                        # Single classifier decides routing (ROUTING.md §5). Desktop route
                        # needs the foreground console -> nudge. mcp/browser routes are
                        # profile-independent -> proceed headlessly without switching.
                        decision = routing.classify_goal(goal)
                        if decision.is_background_safe:
                            # TODO(Phase 2): when route == "mcp", dispatch directly to the
                            # MCP handler instead of hinting the browser. For now both
                            # background-safe routes proceed via the headless browser hint.
                            log_message(f"[Router] Profile B is background; '{decision.route}' route is background-safe ({decision.reason}). Proceeding headlessly.")
                            background_headless_hint = True
                        else:
                            log_message("[Failsafe Active] Profile B is in the background! Proactively pausing visual computer use.")
                            log_message("[Notch UI] Prompting user via Notch to switch to Profile B...")
                            
                            agent_state.nudge_message = "Please fast-user-switch to Profile B to allow visual tasks!"
                            agent_state.status = "waiting_for_user"
                            resume_event.clear()
                            
                            await resume_event.wait()
                            agent_state.nudge_message = ""
                            agent_state.status = "working"
                            log_message("[Loop] Resuming visual computer use loop after user response.")
                            # Re-evaluate the step after user switches profiles
                            continue
            except Exception as se:
                log_message(f"[Warning] Failed to query active console status: {se}")

            log_message(f"[Step {step}] Grabbing screenshot from Agent-Server...")
            
            # Capture Screenshot
            try:
                frame_response = await http_client.get(f"{agent_server_url}/frame.jpg")
                if frame_response.status_code != 200:
                    raise Exception(f"Failed to fetch frame: HTTP {frame_response.status_code}")
                image_bytes = frame_response.content
            except Exception as e:
                log_message(f"[!] Screenshot fetch error: {e}. Retrying in 2s...")
                await asyncio.sleep(2)
                continue
                
            system_prompt = (
                "You are the visual brain of Doppelgänger OS, executing on a macOS screen.\n"
                "Your objective is to help the user complete the following goal: '{goal}'.\n\n"
                "You are controlling the screen via coordinate clicks, keystrokes, and typing.\n"
                "The screen resolution size is standard 1440x900 points. Output all x coordinates "
                "between 0 and 1440, and y coordinates between 0 and 900.\n\n"
                "Examine the screenshot, formulate your reasoning, and output the next logical step.\n"
                "To LAUNCH an app, click its icon in the Dock (along the bottom) or open Launchpad — "
                "do NOT use Spotlight/command+space (system hotkeys are unreliable when B runs in the "
                "background). App shortcuts like command+c / command+v DO work via action='key'. "
                "To type then submit, use action='type' with BOTH 'text' and 'key'='enter'.\n"
                "If the goal requires researching Reddit or web scraping, output action='browser_use'.\n"
                "Otherwise, interact with the screen elements (clicks, types, scroll, keys) to complete the goal.\n"
                "If the goal has been achieved, select action='completed'."
            ).format(goal=goal)
            
            if background_headless_hint:
                system_prompt += (
                    "\n\nCRITICAL NOTIFICATION: Profile B is currently in the background. "
                    "All global visual desktop actions (pyautogui clicks, types, keys) are STRICTLY BLOCKED. "
                    "You MUST use the headless browser remote debugging pathway by outputting action='browser_use' "
                    "and specifying Chrome CDP action arguments (navigate, click, type, scroll) in args. "
                    "Do NOT try to click or type globally on the desktop screen. Proceed headlessly."
                )

            if loop_memory_context:
                system_prompt += "\n\n" + loop_memory_context

            log_message(f"[Step {step}] Analyzing screen via Gemini GenAI...")
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model='gemini-3-flash-preview',
                    contents=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type='image/jpeg',
                        ),
                        system_prompt
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "thought": types.Schema(type=types.Type.STRING, description="Your internal reasoning steps"),
                                "action": types.Schema(
                                    type=types.Type.STRING, 
                                    enum=["click", "type", "key", "noop", "scroll", "browser_use", "completed"],
                                    description="The action verb to execute"
                                ),
                                "args": types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "x": types.Schema(type=types.Type.INTEGER, description="X coordinate (0-1440)"),
                                        "y": types.Schema(type=types.Type.INTEGER, description="Y coordinate (0-900)"),
                                        "text": types.Schema(type=types.Type.STRING, description="Text string to type"),
                                        "key": types.Schema(type=types.Type.STRING, description="Special key name like 'enter', 'tab'"),
                                        "url": types.Schema(type=types.Type.STRING, description="URL string for browser navigation"),
                                        "selector": types.Schema(type=types.Type.STRING, description="CSS selector for browser clicks/typing")
                                    }
                                )
                            },
                            required=["thought", "action"]
                        )
                    )
                )
                
                prediction = {}
                try:
                    prediction = json.loads(response.text)
                except Exception as je:
                    log_message(f"[!] JSON parse error on response: {response.text}")
                    prediction = {"thought": "Fall back to completed due to formatting error", "action": "completed"}
                
                thought = prediction.get("thought", "")
                action = prediction.get("action", "noop")
                args = prediction.get("args", {})
                
                log_message(f"[Brain] Thought: {thought}")
                log_message(f"[Brain] Action: {action} (args={args})")
                
                if action == "completed":
                    log_message("[x] Goal accomplished! Stopping loop.")
                    
                    # Log final memory row to BigQuery
                    log_message("[BigQuery] Saving action log to memory table...")
                    bq_save_memory(
                        memory_type="action_log",
                        content=f"Completed hybrid goal: '{goal}' successfully."
                    )
                    break
                    
                # Handle browser_use pathway (GATE 5 & 6)
                if action == "browser_use":
                    browser_action = "read"
                    if args.get("url"):
                        browser_action = "navigate"
                    elif args.get("text"):
                        browser_action = "type"
                    elif args.get("key"):
                        browser_action = "key"
                    elif args.get("selector") or (args.get("x") is not None and args.get("y") is not None):
                        browser_action = "click"
                        
                    log_message(f"[Browser Use] Dispatching browser action '{browser_action}' with args {args} to agent-server...")
                    
                    cmd_payload = CommandModel(
                        path="browser_use",
                        action=browser_action,
                        args=args
                    )
                    
                    cmd_response = await http_client.post(
                        f"{agent_server_url}/command",
                        json=cmd_payload.model_dump(),
                        timeout=30.0
                    )
                    
                    if cmd_response.status_code != 200:
                        log_message(f"[!] Browser Use command failed: HTTP {cmd_response.status_code}")
                    else:
                        res_data = cmd_response.json()
                        result_info = res_data.get("result", {})
                        
                        if browser_action == "read":
                            posts = result_info.get("posts", [])
                            log_message(f"[Browser Use] Scrape successful! Found {len(posts)} posts.")
                            
                            if posts:
                                # 1. Summarize posts
                                summary_prompt = (
                                    "Write a beautiful, highly professional and detailed newsletter-style digest summary "
                                    "of the following 3 hot Machine Learning posts. Use markdown formatting with clear bold headings, "
                                    "bulleted insights, and clean URLs:\n\n"
                                )
                                for idx, p in enumerate(posts, 1):
                                    summary_prompt += f"{idx}. Title: {p['title']}\n   Link: {p['url']}\n\n"
                                    
                                log_message("[Brain] Summarizing Reddit posts via Gemini...")
                                sum_response = await asyncio.to_thread(
                                    client.models.generate_content,
                                    model='gemini-3-flash-preview',
                                    contents=summary_prompt
                                )
                                summary_text = sum_response.text
                                log_message(f"[Brain] Generated Summary:\n{summary_text}")
                                
                                # 2. Append to Google Doc
                                doc_id = os.getenv("GOOGLE_DOC_ID")
                                if doc_id:
                                    log_message(f"[Google Docs] Appending summary to Doc: {doc_id}...")
                                    success_doc = mcp_google.append_to_google_doc(doc_id, f"\n\n--- REDDIT MACHINE LEARNING DIGEST ---\n\n{summary_text}")
                                    if success_doc:
                                        log_message("[Google Docs] Successfully synced to Cloud Document.")
                                    else:
                                        log_message("[!] Google Docs sync failed.")
                                        
                                # 3. Append row to Google Sheet
                                sheet_id = os.getenv("GOOGLE_SHEET_ID")
                                if sheet_id:
                                    log_message(f"[Google Sheets] Appending log row to Sheet: {sheet_id}...")
                                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    doc_link = f"https://docs.google.com/document/d/{doc_id}/edit" if doc_id else "N/A"
                                    row_values = [
                                        timestamp, 
                                        "Machine Learning Subreddit Research", 
                                        f"Scraped {len(posts)} posts", 
                                        doc_link, 
                                        "Completed Successfully"
                                    ]
                                    success_sheet = mcp_google.append_to_google_sheet(sheet_id, row_values)
                                    if success_sheet:
                                        log_message("[Google Sheets] Successfully synced log row.")
                                    else:
                                        log_message("[!] Google Sheets sync failed.")
                                        
                                # 4. Save to BigQuery Memory table
                                log_message("[BigQuery] Saving action log to memory table...")
                                bq_save_memory(
                                    memory_type="action_log",
                                    content=f"Scraped r/MachineLearning. Top post: '{posts[0]['title']}'."
                                )
                                
                            log_message("[x] Scraping, summarizing, and Cloud Doc/Sheet writing completed!")
                            break
                        else:
                            detail = result_info.get("detail", "success")
                            log_message(f"[Browser Use] Executed successfully: {detail}")
                            continue
                    
                # standard command dispatch to agent-server Port 8421
                log_message(f"[Executor] Executing action '{action}' on Agent-Server...")
                cmd_payload = CommandModel(
                    path="computer_use",
                    action=action,
                    args=args
                )
                
                cmd_response = await http_client.post(
                    f"{agent_server_url}/command",
                    json=cmd_payload.model_dump(),
                    timeout=15.0
                )
                
                if cmd_response.status_code != 200:
                    log_message(f"[!] Command post failed: HTTP {cmd_response.status_code}")
                else:
                    res_data = cmd_response.json()
                    screen_state = res_data.get("screen_state")
                    if screen_state == "background_lock":
                        log_message("[Failsafe Active] Profile B is in the background! Visual computer use is blocked.")
                        log_message("[Notch UI] Prompting user via Notch to switch to Profile B...")
                        
                        agent_state.nudge_message = "Please fast-user-switch to Profile B to allow visual tasks!"
                        agent_state.status = "waiting_for_user"
                        resume_event.clear()
                        
                        await resume_event.wait()
                        agent_state.nudge_message = ""
                        agent_state.status = "working"
                        log_message("[Loop] Resuming visual computer use loop after user response.")
                        continue
                        
                    log_message(f"[Executor] Command result: {res_data.get('result', {}).get('detail', 'done')}")
                    
            except Exception as e:
                log_message(f"[!] Brain failure: {e}")
                
            await asyncio.sleep(2)
            
        log_message("[Loop] Completed tasks execution pipeline.")
        agent_state.status = "completed"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8420, reload=True)
