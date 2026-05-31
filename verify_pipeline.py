#!/usr/bin/env python3
import time
import httpx
import sys

def run_verification():
    print("="*60)
    print("DOPPELGÄNGER OS — AUTOMATED PIPELINE VERIFIER")
    print("="*60)
    
    orchestrator_url = "http://127.0.0.1:8420"
    
    # 1. Check Health
    try:
        res = httpx.get(f"{orchestrator_url}/")
        print(f"[x] Orchestrator Health Check: {res.status_code} - {res.json()}")
    except Exception as e:
        print(f"[!] Orchestrator Health Check Failed: {e}")
        print("Please verify that the orchestrator is running on Port 8420.")
        sys.exit(1)
        
    # 2. Trigger instruction
    goal = "Summarize Machine Learning subreddit"
    print(f"\n[*] Triggering goal: '{goal}'...")
    try:
        res = httpx.post(f"{orchestrator_url}/instruction", json={"goal": goal})
        print(f"[x] Instruction Response: {res.status_code} - {res.json()}")
    except Exception as e:
        print(f"[!] Failed to post instruction: {e}")
        sys.exit(1)
        
    # 3. Poll State until completed
    print("\n[*] Polling agent-state logs in real-time:")
    seen_logs = 0
    max_polls = 60
    for poll in range(max_polls):
        time.sleep(1.5)
        try:
            state_res = httpx.get(f"{orchestrator_url}/state")
            state_data = state_res.json()
            status = state_data.get("status")
            nudge = state_data.get("nudge_message")
            logs = state_data.get("logs", [])
            
            # Print new logs
            if len(logs) > seen_logs:
                for line in logs[seen_logs:]:
                    print(f"  {line}")
                seen_logs = len(logs)
                
            if status == "completed":
                print(f"\n[x] Pipeline execution completed successfully!")
                break
            elif status == "waiting_for_user":
                print(f"\n[!] Agent is waiting for user! Nudge: '{nudge}'")
                # Automatically reply to keep it hands-free
                print("[*] Simulating user response to nudge...")
                httpx.post(f"{orchestrator_url}/instruction", json={"goal": "Alice <alice@example.com>"})
                
        except Exception as e:
            print(f"[!] Polling state error: {e}")
            break
    else:
        print("\n[!] Polling timed out before completion.")
        
    print("="*60)
    print("VERIFICATION COMPLETED")
    print("="*60)

if __name__ == "__main__":
    run_verification()
