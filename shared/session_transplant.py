import os
import json
import httpx
import websockets
import asyncio

# Whitelist of domains allowed for session cookie transplants
COOKIE_DOMAIN_WHITELIST = ["reddit.com", ".reddit.com", "github.com", ".github.com"]

async def extract_cookies_from_profile_a(port: int = 9223) -> list:
    """
    Connects to Profile A Chrome remote debugging session on Port 9223,
    and extracts active session cookies using standard CDP Network.getAllCookies.
    Filters and returns cookies matching the COOKE_DOMAIN_WHITELIST.
    """
    print(f"[Session Transplant] Attempting to extract cookies from Profile A Chrome on Port {port}...")
    try:
        # 1. Fetch active targets list from CDP
        async with httpx.AsyncClient() as client:
            res = await client.get(f"http://127.0.0.1:{port}/json/list")
            if res.status_code != 200:
                print(f"[!] CDP targets list failed with status: {res.status_code}")
                return []
            targets = res.json()
            
        # Locate target with active debugger
        ws_url = None
        for t in targets:
            if "webSocketDebuggerUrl" in t:
                ws_url = t["webSocketDebuggerUrl"]
                break
                
        if not ws_url:
            print("[!] No active webSocketDebuggerUrl found in Chrome targets.")
            return []
            
        # 2. Open WebSocket connection to CDP target
        print(f"[Session Transplant] Connecting to CDP WebSocket: {ws_url}")
        async with websockets.connect(ws_url) as websocket:
            cmd = {
                "id": 1,
                "method": "Network.getAllCookies",
                "params": {}
            }
            await websocket.send(json.dumps(cmd))
            
            raw_response = await websocket.recv()
            response = json.loads(raw_response)
            
            if "error" in response:
                print(f"[!] CDP command error: {response['error']}")
                return []
                
            cookies = response.get("result", {}).get("cookies", [])
            print(f"[Session Transplant] Successfully retrieved {len(cookies)} total cookies.")
            
            # 3. Filter cookies against whitelisted domains
            filtered_cookies = []
            for c in cookies:
                domain = c.get("domain", "")
                is_whitelisted = any(domain.endswith(w) or w.endswith(domain) for w in COOKIE_DOMAIN_WHITELIST)
                if is_whitelisted:
                    filtered_cookies.append(c)
                    
            print(f"[Session Transplant] Kept {len(filtered_cookies)} whitelisted cookies for transplant.")
            return filtered_cookies
            
    except Exception as e:
        print(f"[!] Session Transplant extraction failure: {e}")
        return []
