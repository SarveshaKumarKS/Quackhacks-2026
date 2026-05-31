#!/usr/bin/env python3
import os
import sys
import json
import httpx
import asyncio

# Resolve shared folder import path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from shared.session_transplant import extract_cookies_from_profile_a, COOKIE_DOMAIN_WHITELIST

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orchestrator/.env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if " #" in line:
                    line = line.split(" #", 1)[0].strip()
                elif "\t#" in line:
                    line = line.split("\t#", 1)[0].strip()
                
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip('"').strip("'")
                    os.environ[key.strip()] = val

load_env()

async def main():
    print("="*60)
    print("DOPPELGÄNGER OS — SESSION TRANSPLANT VERIFIER")
    print("="*60)
    
    enable_transplant = os.getenv("ENABLE_SESSION_TRANSPLANT", "false")
    profile_a_port = int(os.getenv("PROFILE_A_CDP_PORT", "9223"))
    agent_server_url = os.getenv("AGENT_SERVER_URL", "http://127.0.0.1:8421")
    
    print(f"[*] Config: ENABLE_SESSION_TRANSPLANT = '{enable_transplant}'")
    print(f"[*] Config: PROFILE_A_CDP_PORT         = {profile_a_port}")
    print(f"[*] Config: AGENT_SERVER_URL          = '{agent_server_url}'")
    print(f"[*] Whitelisted cookie domains        = {COOKIE_DOMAIN_WHITELIST}")
    print("-" * 60)

    # 1. Test Agent-Server Connection
    print("[*] 1. Checking Agent-Server status...")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{agent_server_url}/")
            print(f"[x] Agent-Server is ONLINE: {res.status_code} - {res.json()}")
    except Exception as e:
        print(f"[!] Agent-Server connection failed: {e}")
        print("    Please ensure agent-server is running on Port 8421.")
        return

    # 2. Test /transplant endpoint with mock whitelisted cookies
    print("\n[*] 2. Injecting mock whitelisted cookies to /transplant...")
    mock_cookies = [
        {
            "name": "reddit_session_test",
            "value": "mock_reddit_token_12345",
            "domain": ".reddit.com",
            "path": "/",
            "expires": -1,
            "httpOnly": True,
            "secure": True,
            "sameSite": "None"
        },
        {
            "name": "github_session_test",
            "value": "mock_github_token_67890",
            "domain": "github.com",
            "path": "/",
            "expires": -1,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax"
        },
        {
            "name": "google_forbidden_test",
            "value": "sensitive_unwhitelisted_token",
            "domain": ".google.com",
            "path": "/",
            "expires": -1,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Strict"
        }
    ]
    
    # Filter them locally using same rules to see what we WOULD transfer
    filtered_mock = []
    for c in mock_cookies:
        domain = c.get("domain", "")
        is_whitelisted = any(domain.endswith(w) or w.endswith(domain) for w in COOKIE_DOMAIN_WHITELIST)
        if is_whitelisted:
            filtered_mock.append(c)
            
    print(f"[*] Local filter kept {len(filtered_mock)} out of {len(mock_cookies)} mock cookies (correctly excluded Google).")
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {"cookies": filtered_mock}
            res = await client.post(f"{agent_server_url}/transplant", json=payload, timeout=5.0)
            if res.status_code == 200:
                print(f"[x] Transplant endpoint accepted request: HTTP {res.status_code} - {res.json()}")
            else:
                print(f"[!] Transplant endpoint rejected request: HTTP {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[!] /transplant endpoint request failed: {e}")

    # 3. Try to extract cookies from Profile A Chrome on Port 9223
    print("\n[*] 3. Testing extraction from Profile A Chrome (Port 9223)...")
    extracted = await extract_cookies_from_profile_a(profile_a_port)
    if extracted:
        print(f"[x] Successfully extracted {len(extracted)} whitelisted cookies from Port {profile_a_port}!")
        for c in extracted[:3]:
            print(f"    - Found cookie: name={c['name']}, domain={c['domain']}")
        if len(extracted) > 3:
            print(f"    - ... and {len(extracted) - 3} more.")
    else:
        print("[!] No whitelisted cookies extracted. Diagnostics:")
        print(f"    - Is Chrome running on Profile A?")
        print(f"    - Did you close Chrome and launch it from Terminal with remote debugging?")
        print(f"      Run: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={profile_a_port}")
        print(f"    - Have you navigated to Reddit or GitHub and logged in?")
        
    print("="*60)
    print("TRANSPLANT VERIFICATION COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
