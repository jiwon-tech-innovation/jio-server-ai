import httpx
import asyncio
from bs4 import BeautifulSoup
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ClassifyResponse, ClassifyRequest

def parse_html(html_content: str) -> str:
    """
    CPU-bound parsing of HTML. Should be run in executor.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.title.string.strip() if soup.title else "No Title"
        
        # Try to find description
        desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        description = desc_tag['content'].strip() if desc_tag else "No Description"
        
        return f"Page Title: {title}\nPage Description: {description}"
    except Exception as e:
        return f"Parsing Error: {str(e)}"

async def perform_web_search(query: str) -> str:
    """
    Searches the web for the query to provide context.
    Uses DuckDuckGo Search (No API Key).
    """
    print(f"🔎 [Search] Fallback triggered for: {query}")
    try:
        # Run blocking IO in executor
        loop = asyncio.get_running_loop()
        def _search():
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                return results
        
        results = await loop.run_in_executor(None, _search)
        
        if not results:
            return "No search results found."
            
        summary = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        print(f"🔎 [Search] Results:\n{summary[:200]}...")
        return f"Web Search Context ({query}):\n{summary}"
        
    except Exception as e:
        print(f"⚠️ [Search] Failed: {e}")
        return f"Search Error: {str(e)}"

async def fetch_url_metadata(url: str) -> str:
    """
    Fetches the Title and Description of a URL asynchronously using httpx.
    """
    try:
        if not url.startswith("http"):
            url = "https://" + url
            
        print(f"DEBUG: Fetching URL (Async): {url}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                print(f"DEBUG: Failed to fetch URL. Status: {response.status_code}")
                return f"URL: {url} (Unreachable, Status: {response.status_code})"
            
            # Offload heavy parsing to thread pool
            loop = asyncio.get_running_loop()
            extracted_info = await loop.run_in_executor(None, parse_html, response.text)
            
            full_context = f"URL: {url}\n{extracted_info}"
            print(f"DEBUG: Extracted Info:\n{full_context}")
            return full_context

    except Exception as e:
        print(f"DEBUG: Scraping Error: {e}")
        return f"URL: {url} (Error fetching: {str(e)})"

# =============================================================================
# Fast Path Logic (Optimization)
# =============================================================================

KNOWN_STUDY_APPS = {
    "Code.exe", "idea64.exe", "studio64.exe", "pycharm64.exe", "sublime_text.exe",
    "WindowsTerminal.exe", "cmd.exe", "powershell.exe", "Obsidian.exe", "Notion.exe"
}

KNOWN_PLAY_APPS = {
    "League of Legends.exe", "RiotClientServices.exe", "Steam.exe", "steamwebhelper.exe",
    "Overwatch.exe", "MapleStory.exe", "Discord.exe", "KakaoTalk.exe"
}

KNOWN_STUDY_DOMAINS = [
    "github.com", "stackoverflow.com", "docs.python.org", "claude.ai", "chatgpt.com",
    "google.com", "notion.so", "programmers.co.kr", "baekjoon.online"
]

KNOWN_PLAY_DOMAINS = [
    "netflix.com", "youtube.com/shorts", "twitch.tv", "afreecatv.com",
    "steamcommunity.com", "op.gg", "fow.kr"
]

def check_fast_path(process_name: str, window_title: str, url: str) -> ClassifyResponse | None:
    """
    Checks if the content matches known lists to bypass LLM.
    Returns ClassifyResponse if matched, None otherwise.
    """
    # 1. Process Name Check
    if process_name in KNOWN_STUDY_APPS:
        return ClassifyResponse(
            result="STUDY", 
            state="STUDY", 
            confidence=1.0, 
            reason=f"Known Study App: {process_name}"
        )
    
    if process_name in KNOWN_PLAY_APPS:
        return ClassifyResponse(
            result="PLAY", 
            state="PLAY", 
            confidence=1.0, 
            reason=f"Known Game/Chat App: {process_name}"
        )

    # 2. URL Check
    if url:
        # Pre-process URL
        clean_url = url.replace("https://", "").replace("http://", "").lower()
        
        for stud in KNOWN_STUDY_DOMAINS:
            if stud in clean_url:
                 return ClassifyResponse(
                    result="STUDY", 
                    state="STUDY", 
                    confidence=1.0, 
                    reason=f"Known Study Site: {stud}"
                )
        
        for play in KNOWN_PLAY_DOMAINS:
             if play in clean_url:
                 return ClassifyResponse(
                    result="PLAY", 
                    state="PLAY", 
                    confidence=1.0, 
                    reason=f"Known Play Site: {play}"
                )
    
    return None

async def classify_content(request: ClassifyRequest) -> ClassifyResponse:
    """
    Classifies content as STUDY or PLAY.
    Tries Fast Path first, then falls back to Claude 3.5 Haiku.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.0)
    parser = PydanticOutputParser(pydantic_object=ClassifyResponse)

    # 1. Format Context & Prepare Fast Path Vars
    context_lines = []
    final_content = "Unknown Content"
    proc_name = "Unknown"
    win_title = ""
    target_url = ""

    # [MODE SWITCH] Check content_type
    if request.content_type == "URL" and request.content:
        # Async Fetch (Simulated or Real)
        target_url = request.content
        # NOTE: We fetch metadata later if needed, but for fast path we just check URL string
        final_content = request.content
        proc_name = "Browser" # Default for URL mode
        
    elif request.process_info:
        # Default Window Mode
        proc_name = request.process_info.process_name
        win_title = request.process_info.window_title
        final_content = f"{proc_name} - {win_title}"

    # ==========================
    # ⚡ FAST PATH CHECK
    # ==========================
    fast_result = check_fast_path(proc_name, win_title, target_url)
    if fast_result:
        print(f"⚡ [FastPath] Matched: {fast_result.result} ({fast_result.reason})")
        # Still run side-effects (Memory/Chat) if needed? 
        # For now, let's allow the flow to continue to side-effects below, 
        # OR just acknowledge that side-effects logic is coupled with LLM result vars.
        # Ideally, we return this check immediately, but we need to populate 'result' variable for the shared logic below.
        result = fast_result
    else:
# ... (Imports at top, not shown here but needed: from duckduckgo_search import DDGS)

        # ==========================
        # 🐢 SLOW PATH (LLM)
        # ==========================
        
        # 1. Initial Context Buildup
        if request.content_type == "URL" and request.content:
             url_context = await fetch_url_metadata(request.content)
             context_lines.append(url_context)
        
        elif request.process_info:
            context_lines.append(f"Process Name: {proc_name}")
            context_lines.append(f"Window Title: {win_title}")

            # Additional Process Context
            if request.media_info:
                media_str = f"{request.media_info.artist} - {request.media_info.title} ({request.media_info.app})"
                context_lines.append(f"Media Playing: {media_str}")

            if request.windows:
                clean_windows = [w for w in request.windows if w]
                context_lines.append(f"Open Windows: {', '.join(clean_windows)}")

            if request.system_metrics:
                cpu = request.system_metrics.cpu_percent
                uptime = request.system_metrics.uptime_seconds
                context_lines.append(f"System: CPU {cpu}%, Uptime {int(uptime//60)}m")
                if cpu > 85.0:
                    context_lines.append("Note: System is under heavy load.")

    # ==========================
    # 🐢 SLOW PATH (LLM)
    # ==========================
    
    # 1. Initial Context Buildup
    if request.content_type == "URL" and request.content:
         url_context = await fetch_url_metadata(request.content)
         context_lines.append(url_context)
    
    elif request.process_info:
        context_lines.append(f"Process Name: {proc_name}")
        context_lines.append(f"Window Title: {win_title}")

        # Additional Process Context
        if request.media_info:
            media_str = f"{request.media_info.artist} - {request.media_info.title} ({request.media_info.app})"
            context_lines.append(f"Media Playing: {media_str}")

        if request.windows:
            clean_windows = [w for w in request.windows if w]
            context_lines.append(f"Open Windows: {', '.join(clean_windows)}")

        if request.system_metrics:
            cpu = request.system_metrics.cpu_percent
            uptime = request.system_metrics.uptime_seconds
            context_lines.append(f"System: CPU {cpu}%, Uptime {int(uptime//60)}m")
            if cpu > 85.0:
                context_lines.append("Note: System is under heavy load.")

    prompt_context = "\n".join(context_lines)

    prompt = PromptTemplate(
        template="""
You are JIAA's strict but fair study supervisor.
Your goal is to distinguish between STUDY (Productive) and PLAY (Distraction) based on Screen/URL Context.

Input Context:
{content}

*** CRITICAL RULES ***
1. **URL Analysis**:
   - "Code", "GitHub", "StackOverflow", "Docs" -> **STUDY**.
   - "YouTube" (Learning/Coding channels) -> **STUDY**.
   - "YouTube" (Entertainment/Shorts) -> **PLAY**.
   - "Netflix", "Shopping" -> **PLAY**.

2. **Process Analysis**:
   - `idea64.exe`, `Code.exe`, `Terminal` -> **STUDY**.
   - `League of Legends.exe`, `Steam.exe`, `Discord` -> **PLAY**.
   - **Unknown Games**: If web search indicates it's a "video game", "MMORPG", or "Steam game" -> **PLAY**.

Output JSON Only.
{format_instructions}
        """,
        input_variables=["content"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser

    try:
        # 1st Pass: Classify
        result = await chain.ainvoke({
            "content": prompt_context
        })
        
        # ==========================
        # 🔎 SEARCH FALLBACK
        # ==========================
        # If Low Confidence regarding "UNKNOWN" or potentially misclassified
        if result.confidence < 0.8 or result.result == "UNKNOWN":
            search_query = ""
            if request.content_type == "URL":
                # Extract domain name for cleaner search maybe? Or just use URL title if available
                pass # Usually URL title is enough, handled by fetch_url_metadata
            elif request.process_info:
                 # Search: "{ProcessName} {WindowTitle} what is this"
                 search_query = f"{proc_name} {win_title} software what is this"
            
            if search_query:
                print(f"🤔 [Classifier] Low Confidence ({result.confidence}). Searching: {search_query}")
                search_ctx = await perform_web_search(search_query)
                
                # Re-run LLM with new context
                new_context = prompt_context + "\n\n" + search_ctx
                result = await chain.ainvoke({
                    "content": new_context
                })
                print(f"✅ [Classifier] Re-evaluated: {result.result} (Conf: {result.confidence})")

    except Exception as e:
        print(f"Classifier Error: {e}")
        return ClassifyResponse(result="UNKNOWN", state="UNKNOWN", reason=str(e), confidence=0.0)

    
    # Common Logic (Memory, Jarvis, Control)
    result.state = result.result 

    # [CONTROL] Logic Variables
    jarvis_message = None
    kill_command = None
    trigger_chat = False
    chat_prompt = ""

    # [MEMORY INTEG] Save Event & [JARVIS] Proactive Feedback
    try:
        from app.services.memory_service import memory_service
        from app.services import chat 
        from app.schemas.intelligence import ChatRequest
        
        # [SOUL] Human-like Overrides
        health_message = None
        # ... (Omitted Health Logic for brevity in URL mode, but kept structure) ...

        if result.result == "PLAY":
            memory_service.save_violation(content=final_content, source="ActiveWindow")
            
            # [DEMO] Only scold if confidence is sufficient (Medium/High)
            if result.confidence >= 0.6:
                trigger_chat = True
                chat_prompt = f"User caught: {final_content}. Violation. Scold them."
            else:
                 print(f"😶 [Classifier] Play detected but Low Confidence ({result.confidence}). Skipped scolding.")

        elif result.result == "STUDY":
            memory_service.save_achievement(content=final_content)
            import random
            if random.random() < 0.2:
                trigger_chat = True
                chat_prompt = f"User studying: {final_content}. Praise them."

            # Execute Chat if triggered
            if trigger_chat and chat_prompt:
                 chat_response = await chat.chat_with_persona(ChatRequest(text=chat_prompt))
                 jarvis_message = chat_response.text
            
            if not result.message and jarvis_message: 
                result.message = jarvis_message

    except Exception as mem_err:
        print(f"DEBUG: Logic/Mem Error: {mem_err}")
    
    # [CONTROL] Kill Logic (Browser Kill is hard via URL content, but we can try)
    if result.result == "PLAY" and result.confidence > 0.75: 
        blacklist = ["League of Legends", "Netflix", "Steam"]
        # If URL mode, we might not have process name, but 'final_content' has URL.
        # Simple keyword match
        if any(b.lower() in final_content.lower() for b in blacklist):
            kill_command = "KILL"
            result.message = f"Detected {final_content}. Closing it."
    
    if kill_command:
        result.command = kill_command
    
    return result

