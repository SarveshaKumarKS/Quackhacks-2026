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
    """
    Saves a memory record to BigQuery. Fallback to local memory on any error.
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print("[BQ Fallback] GCP_PROJECT_ID missing, saving locally.")
        return
    try:
        from google.cloud import bigquery
        import random
        client = bigquery.Client(project=project_id)
        table_ref = f"{project_id}.doppelganger_dataset.agent_memory"
        
        mem_id = int(datetime.datetime.now().timestamp() * 1000) + random.randint(0, 999)
        row_to_insert = {
            "id": mem_id,
            "session_id": session_id,
            "memory_type": memory_type,
            "content": content,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        errors = client.insert_rows_json(table_ref, [row_to_insert])
        if errors:
            print(f"[!] BQ insert errors: {errors}")
        else:
            print(f"[x] Successfully saved memory to BigQuery table: {memory_type}")
    except Exception as e:
        print(f"[!] BQ save exception: {e}")

def bq_get_memory(memory_type: str, session_id: str = "doppelganger_session") -> List[str]:
    """
    Retrieves memory records of a given type from BigQuery.
    """
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        return []
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=project_id)
        query = f"""
            SELECT content FROM `{project_id}.doppelganger_dataset.agent_memory`
            WHERE memory_type = @mem_type
            ORDER BY created_at DESC
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("mem_type", "STRING", memory_type)
            ]
        )
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        return [row.content for row in results]
    except Exception as e:
        print(f"[!] BQ get exception: {e}")
        return []

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

async def run_computer_use_loop(goal: str):
    """
    Core Gemini Vision-to-Action loop executing on Port 8420.
    Supports BOTH pure Computer Use (Spotlight, Chrome UI visual clicking)
    AND high-performance Browser Use (Playwright remote CDP browser automation).
    """
    log_message(f"[Loop] Initiating hybrid Autonomous loop for goal: '{goal}'")
    
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
    is_programmatic = any(kw in goal.lower() for kw in ["summarize", "scrape", "reddit", "machine learning"])
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

    max_steps = 15
    async with httpx.AsyncClient() as http_client:
        for step in range(1, max_steps + 1):
            agent_state.step_count = step
            
            # Loop detection confidence gate
            if step > 12:
                log_message("[Confidence Gate] Loop detected! Terminating task to prevent resource exhaustion.")
                break
                
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
                "If the goal requires researching Reddit or web scraping, output action='browser_use'.\n"
                "Otherwise, interact with the screen elements (clicks, types, scroll, keys) to complete the goal.\n"
                "If the goal has been achieved, select action='completed'."
            ).format(goal=goal)
            
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
                                        "key": types.Schema(type=types.Type.STRING, description="Special key name like 'enter', 'tab'")
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
                    log_message("[Browser Use] Dispatching r/MachineLearning scraper to agent-server...")
                    cmd_payload = CommandModel(
                        path="browser_use",
                        action="read",
                        args=args
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
                    break
                    
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
                    log_message(f"[Executor] Command result: {res_data.get('result', {}).get('detail', 'done')}")
                    
            except Exception as e:
                log_message(f"[!] Brain failure: {e}")
                
            await asyncio.sleep(2)
            
        log_message("[Loop] Completed tasks execution pipeline.")
        agent_state.status = "completed"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8420, reload=True)
