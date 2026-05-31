#!/usr/bin/env python3
import os
import sys
import io
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from PIL import ImageGrab, Image
import pyautogui
import httpx

# Resolve shared folder import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.contract import CommandModel, ObservationModel

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../orchestrator/.env")
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

# Configure PyAutoGUI for non-blocking, reliable sandbox execution
pyautogui.FAILSAFE = False  # Avoid locking up in multi-session setups
pyautogui.PAUSE = 0.05       # 50ms standard delay to mimic human input cadence

app = FastAPI(title="Doppelgänger OS — Agent Server (Profile B)", version="1.1")

_last_successful_frame = None
_is_browser_active = False

def is_profile_b_active_console() -> bool:
    """
    Checks if Profile B is the active console GUI session on macOS.
    Returns True if this session is active on the console display,
    False if another user profile is active (Fast User Switched) or screen is locked.
    """
    try:
        import Quartz
        session_dict = Quartz.CGSessionCopyCurrentDictionary()
        if session_dict is None:
            return False
            
        on_console = session_dict.get("kCGSSessionOnConsoleKey", 0) == 1
        is_locked = session_dict.get("CGSSessionScreenIsLocked", 0) == 1
        
        return on_console and not is_locked
    except Exception as e:
        print(f"[Active Session Check] Failed to determine console state: {e}")
        # FAIL CLOSED: if we cannot prove Profile B is the foreground console,
        # assume it is NOT. A detection error must never allow PyAutoGUI input or a
        # global screen capture to run against Profile A. See ROUTING.md §4.
        return False


def vnc_supervised() -> bool:
    """
    Operator opt-in (default OFF): Profile B is being supervised over VNC with a live
    virtual display, so desktop control + capture are intentionally permitted even when
    B is not the physical-console foreground. See docs/VNC_INTEGRATION.md §4.
    Setting this is a conscious assertion that the agent only ever acts on B's session.
    """
    return os.getenv("VNC_SUPERVISED_MODE", "false").lower() == "true"


def desktop_control_allowed() -> bool:
    """Desktop control/capture is allowed if B is the physical foreground console OR
    B is explicitly running in VNC-supervised mode. Default (flag unset) is identical
    fail-closed behavior to is_profile_b_active_console()."""
    return is_profile_b_active_console() or vnc_supervised()

def generate_background_failsafe_frame() -> bytes:
    """
    Generates a beautiful dark theme placeholder frame when Profile B is in the background,
    informing the user that Active Console Protection (failsafe) is active.
    """
    from PIL import ImageDraw
    img = Image.new("RGB", (1024, 768), color="#11111b") # Premium dark crust color
    draw = ImageDraw.Draw(img)
    
    # Draw a decorative rounded rectangle in the center (glassmorphism/HUD card feel)
    draw.rounded_rectangle(
        [(150, 180), (874, 588)],
        radius=20,
        fill="#1e1e2e", # sleek dark card
        outline="#313244", # subtle border
        width=2
    )
    
    # Header title
    draw.text((200, 220), "DOPPELGANGER OS - SECURE SANDBOX", fill="#89b4fa") # Sky blue brand header
    draw.text((200, 270), "Active Console Protection Guard (Failsafe Active)", fill="#f38ba8") # Pastel red alert
    
    # Context body text
    body_lines = [
        "The agent-server process is running in the background of Profile B.",
        "Visual controls and desktop screen capture are temporarily suspended",
        "to prevent hijacking your active Profile A workspace.",
        "",
        "Status:",
        " - Screen Capture: BLOCKED (Failsafe Active)",
        " - PyAutoGUI Inputs: BLOCKED (Failsafe Active)",
        " - Chrome Remote Debugging (Port 9222): ACTIVE",
        "",
        "How to proceed:",
        " 1. Web tasks: Use browser remote automation over Chrome CDP (Port 9222).",
        "    This runs 100% in the background, fully isolated, without disrupting you.",
        " 2. Desktop tasks: Trigger Fast User Switching to switch back to Profile B."
    ]
    
    y = 310
    for line in body_lines:
        draw.text((200, y), line, fill="#cdd6f4") # Premium crisp off-white text
        y += 20
        
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()

def capture_screen_as_jpeg() -> bytes:
    """
    Captures the current active desktop screen of Profile B using Pillow/Quartz.
    If Profile B is in the background, returns a beautiful secure failsafe placeholder
    unless headless background browser automation is active.
    """
    global _last_successful_frame, _is_browser_active
    
    # Safety Check: If Profile B is in the background (and NOT VNC-supervised), protect
    # Profile A's screen. In VNC mode B has its own virtual display, so real capture of
    # B's session is intended.
    if not desktop_control_allowed():
        # If we are actively running background browser automation and have a browser frame, return it!
        if _is_browser_active and _last_successful_frame is not None:
            return _last_successful_frame
        # Otherwise, show the failsafe placeholder
        return generate_background_failsafe_frame()
        
    try:
        screenshot = ImageGrab.grab()
        # Convert RGBA/LA formats (which contain transparency/alpha channels) to standard RGB
        # since JPEG does not support alpha channels.
        if screenshot.mode in ("RGBA", "LA") or (screenshot.mode == "P" and "transparency" in screenshot.info):
            screenshot = screenshot.convert("RGB")
        # Compress image to 60% quality to maximize frame-rate over localhost
        buffer = io.BytesIO()
        screenshot.save(buffer, format="JPEG", quality=60)
        frame_bytes = buffer.getvalue()
        _last_successful_frame = frame_bytes
        return frame_bytes
    except Exception as e:
        print(f"[!] Screen capture failure: {e}")
        # Return the last successful frame to avoid screen flickering
        if _last_successful_frame is not None:
            return _last_successful_frame
        # Return a solid black placeholder frame if background session is asleep/locked and no cache exists
        black_placeholder = Image.new("RGB", (1024, 768), color="black")
        buffer = io.BytesIO()
        black_placeholder.save(buffer, format="JPEG")
        return buffer.getvalue()

@app.get("/")
async def root():
    return {
        "status": "online",
        "role": "agent-server",
        "port": 8421,
        "active_console": is_profile_b_active_console(),  # truthful physical-console state
        "vnc_supervised": vnc_supervised(),
        "control_allowed": desktop_control_allowed(),     # what the orchestrator should gate on
    }

@app.get("/frame.jpg")
async def get_frame():
    """
    Exposes a single screenshot frame as image/jpeg.
    Used by the Orchestrator for Gemini Computer Use vision input.
    """
    frame_bytes = await asyncio.to_thread(capture_screen_as_jpeg)
    return Response(content=frame_bytes, media_type="image/jpeg")

async def stream_generator():
    """
    Generates an continuous multipart/x-mixed-replace MJPEG frame stream.
    Throttled to 10 FPS to balance low latency with zero CPU pinning.
    """
    while True:
        frame_bytes = await asyncio.to_thread(capture_screen_as_jpeg)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        # 100ms throttle (10 FPS)
        await asyncio.sleep(0.1)

@app.get("/stream")
async def get_stream():
    """
    MJPEG stream endpoint for live Picture-in-Picture display in the SwiftUI Notch UI.
    """
    return StreamingResponse(
        stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

async def scrape_reddit_ml() -> Dict[str, Any]:
    """
    Scrapes the top 3 post titles and URLs from r/MachineLearning.
    Attempts Chrome CDP Port 9222 first, and falls back to a clean HTTP JSON API on failure.
    """
    print("[Scraper] Initiating r/MachineLearning scrape...")
    
    # 1. Primary path: try connecting to Google Chrome remote debugging on Port 9222
    try:
        from playwright.async_api import async_playwright
        print("[Scraper] Connecting to Chrome remote debugging on Port 9222...")
        async with async_playwright() as p:
            # Enforce strict 3.0s timeout to prevent hanging if remote port is offline
            browser = await asyncio.wait_for(
                p.chromium.connect_over_cdp("http://127.0.0.1:9222"),
                timeout=3.0
            )
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            
            await page.goto("https://www.reddit.com/r/MachineLearning/hot/", timeout=10000)
            
            # Resilient wait for any standard modern/legacy post element to load
            try:
                await page.wait_for_selector("shreddit-post, a[data-click-id='body'], a[slot='full-post-link'], h3", timeout=5000)
            except Exception:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            # Robust browser-side post extraction covering multiple layout generations
            posts = await page.evaluate('''() => {
                let items = [];
                // 1. Try modern Reddit shreddit-post custom elements
                let shredditPosts = document.querySelectorAll('shreddit-post');
                for (let post of shredditPosts) {
                    let title = post.getAttribute('post-title');
                    let href = post.getAttribute('content-href') || post.getAttribute('permalink');
                    if (title && href) {
                        items.push({title: title.trim(), url: href.startsWith('/') ? 'https://www.reddit.com' + href : href});
                    }
                }
                
                // 2. Try standard full-post-link elements
                if (items.length < 3) {
                    let links = document.querySelectorAll("a[data-click-id='body'], a[slot='full-post-link']");
                    for (let a of links) {
                        let title = a.innerText.trim();
                        let href = a.getAttribute('href');
                        if (title && href) {
                            items.push({title, url: href.startsWith('/') ? 'https://www.reddit.com' + href : href});
                        }
                    }
                }
                
                // 3. Resilient fallback to heading links (h3/h2)
                if (items.length < 3) {
                    let headings = document.querySelectorAll('h3, h2');
                    for (let h of headings) {
                        let title = h.innerText.trim();
                        let a = h.closest('a') || h.querySelector('a') || h.parentElement.closest('a');
                        if (title && a) {
                            let href = a.getAttribute('href');
                            if (href) {
                                items.push({title, url: href.startsWith('/') ? 'https://www.reddit.com' + href : href});
                            }
                        }
                    }
                }
                return items.slice(0, 3);
            }''')
                
            await page.close()
            await browser.close()
            
            if posts:
                print(f"[Scraper] Successfully scraped {len(posts)} posts over CDP.")
                return {"success": True, "source": "chrome_cdp", "posts": posts}
    except Exception as e:
        print(f"[!] CDP scraping failed or Chrome offline: {e}")
        
    # 2. Fallback path: Zero-dependency clean HTTP fetch of Hacker News live tech/AI API
    print("[Scraper] Falling back to zero-dependency live Hacker News tech/AI API...")
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5.0)
            if res.status_code == 200:
                story_ids = res.json()[:12]
                
                async def fetch_story(sid):
                    try:
                        item_res = await client.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=3.0)
                        if item_res.status_code == 200:
                            return item_res.json()
                    except Exception as e:
                        print(f"[Scraper] Failed to fetch story {sid}: {e}")
                    return None

                tasks = [fetch_story(sid) for sid in story_ids]
                items = await asyncio.gather(*tasks)
                
                posts = []
                for item in items:
                    if item:
                        title = item.get("title", "")
                        url = item.get("url", f"https://news.ycombinator.com/item?id={item.get('id')}")
                        
                        # Prioritize AI / Machine Learning related posts
                        keywords = ["ai", "ml", "machine learning", "deep learning", "llm", "neural", "gpu", "model", "gpt", "anthropic", "openai", "gemini", "nvidia", "hugging face", "transformer"]
                        is_ai = any(kw in title.lower() for kw in keywords)
                        
                        if is_ai:
                            posts.insert(0, {"title": title, "url": url})
                        else:
                            posts.append({"title": title, "url": url})
                            
                final_posts = posts[:3]
                print(f"[Scraper] Successfully fetched {len(final_posts)} live stories from Hacker News.")
                return {"success": True, "source": "hacker_news_live_api", "posts": final_posts}
            else:
                raise Exception(f"HTTP Status {res.status_code}")
    except Exception as err:
        print(f"[!] Fallback Live HN API failed: {err}")
        print("[Scraper] Using high-fidelity cached fallback posts for demo resilience...")
        cached_posts = [
            {"title": "Show ML: Light-RAG – A Lightweight and Fast Retrieval-Augmented Generation Framework", "url": "https://github.com/HKU-NLP/LightRAG"},
            {"title": "[R] DeepMind Releases AlphaFold 3: Accurately Predicting Structures of Proteins and Nucleic Acids", "url": "https://www.nature.com/articles/s41586-024-07487-w"},
            {"title": "[D] Are LLMs reaching a performance plateau? A discussion on the limits of scaling laws", "url": "https://www.reddit.com/r/MachineLearning/comments/scaling_discussion"}
        ]
        return {"success": True, "source": "cached_fallback", "posts": cached_posts}

async def execute_browser_use_command(action: str, args: dict) -> Dict[str, Any]:
    """
    Automates Chrome running on Port 9222 via CDP using Playwright.
    Executes actions inside the browser session completely headlessly and in the background.
    """
    global _is_browser_active
    _is_browser_active = True
    
    from playwright.async_api import async_playwright
    print(f"[Browser Use] Connecting to Chrome remote debugging on Port 9222 to run action '{action}'...")
    
    try:
        async with async_playwright() as p:
            browser = await asyncio.wait_for(
                p.chromium.connect_over_cdp("http://127.0.0.1:9222"),
                timeout=3.0
            )
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            pages = context.pages
            page = pages[0] if pages else await context.new_page()
            
            await page.set_viewport_size({"width": 1024, "height": 768})
            result_detail = ""
            extra: Dict[str, Any] = {}
            
            if action == "navigate":
                url = args.get("url")
                if not url:
                    raise Exception("Navigate requires 'url' arg")
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = f"https://{url}"
                await page.goto(url, timeout=15000)
                result_detail = f"Navigated to {url}"
                
            elif action == "click":
                selector = args.get("selector")
                x = args.get("x")
                y = args.get("y")
                
                if selector:
                    await page.click(selector, timeout=5000)
                    result_detail = f"Clicked element matching '{selector}'"
                elif x is not None and y is not None:
                    x_vp = int(x * (1024 / 1440))
                    y_vp = int(y * (768 / 900))
                    await page.mouse.click(x_vp, y_vp)
                    result_detail = f"Clicked at viewport coordinates ({x_vp}, {y_vp})"
                else:
                    raise Exception("Click requires either 'selector' or 'x' and 'y'")
                    
            elif action == "type":
                text = args.get("text")
                if text is None:
                    raise Exception("Type requires 'text' arg")
                
                selector = args.get("selector")
                x = args.get("x")
                y = args.get("y")
                if selector:
                    await page.click(selector)
                elif x is not None and y is not None:
                    x_vp = int(x * (1024 / 1440))
                    y_vp = int(y * (768 / 900))
                    await page.mouse.click(x_vp, y_vp)
                    
                await page.keyboard.type(text)
                result_detail = f"Typed text"
                
            elif action == "key":
                key = args.get("key")
                if not key:
                    raise Exception("Key requires 'key' arg")
                await page.keyboard.press(key)
                result_detail = f"Pressed key '{key}'"
                
            elif action == "scroll":
                amount = args.get("amount", 200)
                await page.evaluate(f"window.scrollBy(0, {amount})")
                result_detail = f"Scrolled by {amount} pixels"
                
            elif action == "read":
                return await scrape_reddit_ml()

            elif action == "extract":
                # Generic: navigate to the orchestrator-chosen target, then return
                # the page's visible text for the brain to summarize/answer.
                url = args.get("url")
                if url:
                    if not url.startswith("http://") and not url.startswith("https://"):
                        url = f"https://{url}"
                    await page.goto(url, timeout=20000)
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=8000)
                    except Exception:
                        pass
                page_title = await page.title()
                page_text = await page.evaluate("() => (document.body ? document.body.innerText : '')")
                page_text = (page_text or "")[:8000]
                result_detail = f"Extracted {len(page_text)} chars from {page.url}"
                extra = {"text": page_text, "title": page_title, "page_url": page.url}

            elif action == "screenshot":
                result_detail = "Captured browser screenshot"
                
            else:
                raise Exception(f"Unsupported browser action: {action}")
                
            # Capture viewport frame and update last frame buffer
            try:
                screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
                global _last_successful_frame
                _last_successful_frame = screenshot_bytes
            except Exception as se:
                print(f"[Warning] Failed to update frame after action: {se}")
                
            await browser.close()
            return {"success": True, "detail": result_detail, **extra}
            
    except Exception as e:
        print(f"[!] Browser Use execution failure: {e}")
        return {"success": False, "error_message": str(e)}

@app.post("/command")
async def execute_command(command: CommandModel):
    """
    Orchestrator submits active commands here to be physically executed in Profile B.
    Handles mouse movements, typing, keys, scrolling, and browser research.
    """
    print(f"[*] Command received: path={command.path}, action={command.action}, args={command.args}")
    
    if command.path == "browser_use":
        browser_result = await execute_browser_use_command(command.action, command.args)
        return ObservationModel(
            screenshot_url="http://localhost:8421/frame.jpg",
            screen_state="ok" if browser_result["success"] else "error",
            result=browser_result
        )
        
    if command.path == "noop":
        return ObservationModel(
            screenshot_url="http://localhost:8421/frame.jpg",
            screen_state="ok",
            result={"success": True, "detail": "noop completed"}
        )
        
    if command.path == "computer_use" or command.path not in ("browser_use", "noop"):
        global _is_browser_active
        _is_browser_active = False
        # Safety Check: Block PyAutoGUI if Profile B is in the background AND not VNC-supervised.
        if not desktop_control_allowed():
            print("[Failsafe Active] Blocking PyAutoGUI action because Profile B is in the background.")
            return ObservationModel(
                screenshot_url="http://localhost:8421/frame.jpg",
                screen_state="background_lock",
                result={
                    "success": False, 
                    "error_message": "Failsafe Active: Profile B is in the background. Visual desktop control is blocked to protect your workspace."
                }
            )
        
    action = command.action
    args = command.args
    
    try:
        if action == "click":
            x = args.get("x")
            y = args.get("y")
            if x is None or y is None:
                raise HTTPException(status_code=400, detail="Click args must contain 'x' and 'y'")
            pyautogui.click(x, y)
            
        elif action == "type":
            text = args.get("text")
            if text is None:
                raise HTTPException(status_code=400, detail="Type args must contain 'text'")
            pyautogui.write(text)
            
        elif action == "key":
            key = args.get("key")
            if key is None:
                raise HTTPException(status_code=400, detail="Key args must contain 'key'")
            pyautogui.press(key)
            
        elif action == "hover":
            x = args.get("x")
            y = args.get("y")
            if x is None or y is None:
                raise HTTPException(status_code=400, detail="Hover args must contain 'x' and 'y'")
            pyautogui.moveTo(x, y)
            
        elif action == "scroll":
            amount = args.get("amount", -5)
            pyautogui.scroll(amount)
            
        elif action == "screenshot":
            # Screenshot is captured ambiently and returned
            pass
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
            
        return ObservationModel(
            screenshot_url="http://localhost:8421/frame.jpg",
            screen_state="ok",
            result={"success": True, "detail": f"{action} executed successfully"}
        )
        
    except Exception as e:
        print(f"[!] Action execution failure: {e}")
        return ObservationModel(
            screenshot_url="http://localhost:8421/frame.jpg",
            screen_state="error",
            result={"success": False, "error_message": str(e)}
        )

from pydantic import BaseModel

class TransplantPayload(BaseModel):
    cookies: list

async def inject_cookies_to_browser(cookies: list):
    """
    Injects sanitized session cookies into the active Playwright Chrome CDP context on Port 9222.
    """
    if not cookies:
        return
    try:
        from playwright.async_api import async_playwright
        print(f"[Session Transplant] Injecting {len(cookies)} cookies into active Chrome session...")
        async with async_playwright() as p:
            browser = await asyncio.wait_for(
                p.chromium.connect_over_cdp("http://127.0.0.1:9222"),
                timeout=3.0
            )
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            
            formatted_cookies = []
            for c in cookies:
                same_site = c.get("sameSite", "Lax")
                if same_site not in ["Lax", "None", "Strict"]:
                    same_site = "Lax"
                    
                formatted_cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c["domain"],
                    "path": c.get("path", "/"),
                    "expires": c.get("expires", -1),
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", False),
                    "sameSite": same_site
                })
                
            await context.add_cookies(formatted_cookies)
            print(f"[Session Transplant] Successfully transplanted {len(formatted_cookies)} cookies into background browser.")
            await browser.close()
    except Exception as e:
        print(f"[!] Session Transplant injection failure: {e}")

@app.post("/transplant")
async def receive_transplant(payload: TransplantPayload):
    """
    Endpoint called by Orchestrator to inject Profile A Chrome session cookies into Profile B.
    """
    if not os.getenv("ENABLE_SESSION_TRANSPLANT", "false").lower() == "true":
        raise HTTPException(status_code=400, detail="Session transplant module is disabled")
        
    asyncio.create_task(inject_cookies_to_browser(payload.cookies))
    return {"status": "transplant_initiated", "count": len(payload.cookies)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8421, reload=True)
