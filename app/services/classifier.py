import requests
from bs4 import BeautifulSoup
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.core.llm import get_llm, HAIKU_MODEL_ID
from app.schemas.intelligence import ClassifyResponse, ClassifyRequest

def fetch_url_metadata(url: str) -> str:
    """
    Fetches the Title and Description of a URL.
    Returns a formatted string context.
    """
    try:
        # Timeout 5s, fake User-Agent to avoid bot detection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        print(f"DEBUG: Fetching URL: {url}")
        response = requests.get(url, timeout=5.0, headers=headers)
        
        if response.status_code != 200:
            print(f"DEBUG: Failed to fetch URL. Status: {response.status_code}")
            return f"URL: {url} (Unreachable, Status: {response.status_code})"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "No Title"
        
        # Try to find description
        desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        description = desc_tag['content'].strip() if desc_tag else "No Description"
        
        extracted_info = f"URL: {url}\nPage Title: {title}\nPage Description: {description}"
        print(f"DEBUG: Extracted Info:\n{extracted_info}")
        return extracted_info

    except Exception as e:
        print(f"DEBUG: Scraping Error: {e}")
        return f"URL: {url} (Error fetching: {str(e)})"

async def classify_content(request: ClassifyRequest) -> ClassifyResponse:
    """
    Classifies content as STUDY or PLAY using Claude 3.5 Haiku.
    Relies on Process Name and Window Title. NO KPM.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.0)
    parser = PydanticOutputParser(pydantic_object=ClassifyResponse)

    # 1. Format Context (Process + Window)
    context_lines = []
    
    # Process Info
    proc_name = request.process_info.process_name
    win_title = request.process_info.window_title
    
    context_lines.append(f"Process Name: {proc_name}")
    context_lines.append(f"Window Title: {win_title}")

    # Media Info
    if request.media_info:
        media_str = f"{request.media_info.artist} - {request.media_info.title} ({request.media_info.app})"
        context_lines.append(f"Media Playing: {media_str}")

    # Window List
    if request.windows:
        clean_windows = [w for w in request.windows if w]
        context_lines.append(f"Open Windows: {', '.join(clean_windows)}")

    # [SOUL] System & Human Context Logic
    if request.system_metrics:
        cpu = request.system_metrics.cpu_percent
        uptime = request.system_metrics.uptime_seconds
        context_lines.append(f"System: CPU {cpu}%, Uptime {int(uptime//60)}m")
        if cpu > 85.0:
            context_lines.append("Note: System is under heavy load (User likely compiling or rendering).")

    prompt_context = "\n".join(context_lines)
    final_content = f"{proc_name} - {win_title}"

    prompt = PromptTemplate(
        template="""
You are JIAA's strict but fair study supervisor.
Your goal is to distinguish between STUDY (Productive) and PLAY (Distraction) based on Screen State.

Input Context:
{content}

*** CRITICAL RULES (No Input Metrics) ***
1. **Process Analysis**:
   - `idea64.exe`, `Code.exe`, `pycharm64.exe` -> **STUDY** (Coding).
   - `Discord.exe`, `KakaoTalk.exe` -> **PLAY** (Communication).
   - `League of Legends.exe`, `Steam.exe` -> **PLAY** (Games).
   - `chrome.exe` -> Depends on Title.

2. **Window Title Analysis (Active Window)**:
   - "YouTube" + Title "Spring Boot" -> **STUDY**.
   - "YouTube" + Title "Funny Video" -> **PLAY**.
   - "StackOverflow", "GitHub", "Docs" -> **STUDY**.
   - "Netflix", "Shopping" -> **PLAY**.

Output 'confidence' (0.0-1.0).
Output 'result' (STUDY/PLAY).
Output 'state' (STUDY/PLAY).
Output 'reason'.

{format_instructions}

IMPORTANT: Output ONLY the JSON object. No explanations.
        """,
        input_variables=["content"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser

    try:
        result = await chain.ainvoke({
            "content": prompt_context
        })
        
        # Enforce State consistency
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
            is_busy = False
            if request.system_metrics and request.system_metrics.cpu_percent > 85.0:
                is_busy = True
            
            health_message = None
            if request.system_metrics:
                uptime_min = request.system_metrics.uptime_seconds / 60
                from datetime import datetime
                current_hour = datetime.now().hour
                
                if uptime_min > 50:
                     health_message = "Users has been active for over 50 mins. Remind them to stretch."
                if 2 <= current_hour < 5:
                     health_message = "It is very late (after 2 AM). Scold them to go to sleep for their health."

            # Trigger Logic
            if is_busy:
                result.message = None 
                print("DEBUG: Busy Mode Activated. Silencing.")
            
            elif health_message:
                 trigger_chat = True
                 chat_prompt = f"User context: {final_content}. {health_message}. Say it briefly in Tsundere tone."
                 print(f"DEBUG: Health Message Triggered: {health_message}")

            elif result.result == "PLAY":
                memory_service.save_violation(content=final_content, source="ActiveWindow")
                trigger_chat = True
                chat_prompt = f"User just got caught doing: {final_content} (Process: {proc_name}). This is a VIOLATION. Scold them severely."

            elif result.result == "STUDY":
                 memory_service.save_achievement(content=final_content)
                 # Random Praise (20%)
                 import random
                 if random.random() < 0.2:
                     trigger_chat = True
                     chat_prompt = f"User is studying: {final_content}. Praise them in a Tsundere way."

            # Execute Chat if triggered
            if trigger_chat and chat_prompt:
                 # print(f"DEBUG: Chat Triggered with prompt: {chat_prompt}") 
                 chat_response = await chat.chat_with_persona(ChatRequest(text=chat_prompt))
                 jarvis_message = chat_response.text
            
            # Inject message
            if not result.message and jarvis_message: 
                result.message = jarvis_message

        except Exception as mem_err:
             print(f"DEBUG: Memory/Chat Logic Failed (Likely DB): {mem_err}")
             pass
        
        # [CONTROL] Active Desktop Management (Kill Logic)
        print(f"DEBUG: Kill Check -> Result: {result.result}, Conf: {result.confidence}, Content: {final_content}")

        if result.result == "PLAY" and result.confidence > 0.75: 
             blacklist = ["League of Legends", "Netflix", "Steam", "MapleStory"]
             # Check both title and process
             if any(b in final_content for b in blacklist) or any(b in proc_name for b in blacklist):
                  kill_command = "KILL"
                  if not result.message or "오류" in str(result.message):
                      result.message = f"User is playing {final_content}. I am closing it FORCEFULLY."
                  else:
                      result.message += " (프로그램을 강제로 종료합니다.)"
        
        # Inject command
        if kill_command:
            result.command = kill_command
            result.message += " (프로그램을 강제로 종료합니다.)"
        
        # Inject generated message
        # Note: If chat failed, trigger_chat logic above might have failed to set jarvis_message.
        # But if trigger_chat succeeded inside try block, we need to run chat here if we moved chat call out?
        # WAIT: In my previous refactor, I put chat call inside try block. Let's keep it there or ensure logic flows.
        # Ideally chat call should be inside try block.
        
        # RE-INSERTING CHAT CALL logic inside try block for simplicity in this full replace.
        # Wait, I omitted the Chat execution lines in the try block above. I need to add them back.
        
        return result

    except Exception as e:
        print(f"Classifier Error: {e}")
        return ClassifyResponse(result="UNKNOWN", state="UNKNOWN", reason=f"Classification failed: {str(e)}", confidence=0.0)
