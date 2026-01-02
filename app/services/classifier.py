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
    Performs Deep Analysis for URLs.
    """
    llm = get_llm(model_id=HAIKU_MODEL_ID, temperature=0.0)
    parser = PydanticOutputParser(pydantic_object=ClassifyResponse)

    # 1. Enrich Content (if URL)
    final_content = request.content
    if request.content_type.upper() == "URL" and "http" in request.content:
        # Sync call in async function (optimization: use aiohttp later if heavy load)
        final_content = fetch_url_metadata(request.content)

    prompt = PromptTemplate(
        template="""
You are JIAA's strict but fair study supervisor.
Your goal is to distinguish between STUDY (Productive) and PLAY (Distraction) based on the user's activity.

Input Context:
Type: {content_type}
Content Details:
{content}

*** CRITICAL RULES ***
1. **Deep Analysis**: Look at the Page Title and Description.
   - "YouTube" -> PLAY (Default).
   - "YouTube" + Title "Spring Boot Course" -> STUDY.
   - "YouTube" + Title "Funny Cat Video" -> PLAY.
   - "StackOverflow", "GitHub", "Tech Blog" -> STUDY.
   - "Shopping", "Game Site", "Netflix" -> PLAY.

2. **User Status (Behavior)**:
   - "SLEEPING" or "AWAY" -> PLAY.
   - "CODING" or "TYPING" -> STUDY.

3. **Ambiguity**: If unsure but looks technical (e.g., "Python Documentation"), assume STUDY.

Output 'confidence' (0.0-1.0).

{format_instructions}

IMPORTANT: Output ONLY the JSON object. No explanations, no markdown, no code blocks, no additional text before or after the JSON.
        """,
        input_variables=["content_type", "content"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser

    try:
        result = await chain.ainvoke({
            "content_type": request.content_type,
            "content": final_content
        })
        return result
    except Exception as e:
        # Fallback in case of parsing error or LLM failure
        print(f"Classifier Error: {e}")
        return ClassifyResponse(result="UNKNOWN", reason=f"Classification failed: {str(e)}", confidence=0.0)
