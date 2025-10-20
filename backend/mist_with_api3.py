# ======================
# IMPORTS
# ======================
import os
import json
import asyncio
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llama_cpp import Llama
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache  # Keep this import
from fastapi.responses import PlainTextResponse
from collections import defaultdict, deque
import fasttext
from threading import Lock
import re  # Add this for HTML cleaning


# Ensure deterministic embeddings across runs

ft_lock = Lock()

# ======================
# APP CONFIGURATION
# ======================
app = FastAPI()
@app.on_event("startup")
async def startup_event():
    # Initialize cache
    FastAPICache.init(InMemoryBackend(), prefix="iuc-cache")
    
    global context_cache
    context_cache = {
        "data": None,
        "timestamp": None,
        "lock": asyncio.Lock()
    }
    try:
        raw_data = await fetch_api_data()
        context_cache["data"] = process_speciality_data(raw_data)
        context_cache["timestamp"] = datetime.now()
        print("✅ API data loaded and processed (specialities cleaned)")
        print(f"✅ Endpoints loaded: {list(context_cache['data'].keys())}")
    except Exception as e:
        print(f"❌ Initialization failed: {str(e)}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


#from fastapi.staticfiles import StaticFiles
#from fastapi.responses import FileResponse

# Serve static files from UI/static directory
#app.mount("/static", StaticFiles(directory="/iuc_ai_orientation_agent/UI/static"), name="static")

# Serve the main page
#@app.get("/")
#async def read_index():
#    return FileResponse('/app/UI/index.html')


CACHE_TTL = 604800  # 7 days  

# ======================
# HTML EXTRACTION FOR SPECIALITIES
# ======================

def summarize_speciality_content(full_text: str, max_length: int = 600) -> str:
    """Better summarization that preserves key information"""
    if len(full_text) <= max_length:
        return full_text
    
    # First, extract ALL CAPS sections and their content
    sections = {}
    current_section = "INTRODUCTION"
    current_content = []
    
    lines = full_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line is a section header (ALL CAPS or title case)
        if (line.isupper() or 
            (len(line) < 100 and any(word.isupper() for word in line.split()) and 
             any(keyword in line.upper() for keyword in ['LEVEL', 'PROGRAM', 'PROGRAMME', 'SEMESTER', 'DURATION', 'CREDIT', 'PARTNER INSTITUTION', 'ACCREDITATION', 'STUDENT PROFILE', 'APPLICATION FILE',
                          'PARTENAIRE', 'DIPLOM REQUIS', 'DOSSIER', 'SPÉCIALITÉ', 'CODE', 'NIVEAU' 'CRÉDIT', 'DURÉE', 'ACCRÉDITATION', 'DIPLOME', 'ELEMENT DU DOSSIERS']))):
            
            # Save previous section
            if current_content and current_section:
                sections[current_section] = ' '.join(current_content)
            
            # Start new section
            current_section = line.upper()
            current_content = []
        else:
            current_content.append(line)
    
    # Save the last section
    if current_content and current_section:
        sections[current_section] = ' '.join(current_content)
    
    # If no sections found, use paragraph-based approach
    if not sections or len(sections) == 1:
        paragraphs = [p.strip() for p in full_text.split('\n\n') if p.strip()]
        if paragraphs:
            # Keep first paragraph (introduction)
            intro = paragraphs[0]
            
            # Look for key paragraphs with important information
            key_paragraphs = []
            for para in paragraphs[1:]:
                para_lower = para.lower()
                if any(keyword in para_lower for keyword in 
                      ['diplom', 'dossier', 'admission', 'requis', 'programme','duration', 'durée', 
                       'credit', 'semestre', 'partenaire', 'accréditation']):
                    key_paragraphs.append(para)
                    if len(key_paragraphs) >= 2:  # Max 2 key paragraphs
                        break
            
            # Combine introduction with key paragraphs
            if key_paragraphs:
                summary_parts = [intro] + key_paragraphs
                summary = ' [...] '.join(summary_parts)
            else:
                # Fallback: intro + last paragraph
                summary = f"{intro} [...] {paragraphs[-1]}" if len(paragraphs) > 1 else intro
        else:
            # Simple intelligent truncation
            sentences = re.split(r'[.!?]+', full_text)
            if len(sentences) > 3:
                summary = '. '.join(sentences[:3]) + '...' + '. '.join(sentences[-2:])
            else:
                summary = full_text[:500] + "..."
    else:
        # Build summary from important sections
        important_sections = ['LEVEL', 'PROGRAM', 'PROGRAMME', 'SEMESTER', 'DURATION', 'CREDIT', 'PARTNER INSTITUTION', 'ACCREDITATION', 'STUDENT PROFILE', 'APPLICATION FILE',
                          'PARTENAIRE', 'DIPLOM REQUIS', 'DOSSIER', 'SPÉCIALITÉ', 'CODE', 'NIVEAU' 'CRÉDIT', 'DURÉE', 'ACCRÉDITATION', 'DIPLOME', 'ELEMENT DU DOSSIERS']
        
        summary_parts = []
        for section in important_sections:
            if section in sections:
                content = sections[section]
                # Truncate section content if too long
                if len(content) > 150:
                    content = content[:147] + "..."
                summary_parts.append(f"{section}: {content}")
        
        # If no important sections found, use first 3 sections
        if not summary_parts and sections:
            for i, (section, content) in enumerate(list(sections.items())[:3]):
                if len(content) > 150:
                    content = content[:147] + "..."
                summary_parts.append(f"{section}: {content}")
        
        summary = ' | '.join(summary_parts)
    
    # Final length control
    if len(summary) > max_length:
        # Intelligent truncation at sentence boundary
        if '.' in summary[:max_length-50]:
            last_dot = summary[:max_length-50].rfind('.')
            if last_dot > max_length // 2:
                summary = summary[:last_dot+1] + ".."
            else:
                summary = summary[:max_length-3] + "..."
        else:
            summary = summary[:max_length-3] + "..."
    
    return summary


def summarize_speciality_content7(full_text: str, max_length: int = 300) -> str:
    """Summarize content with structured key-value formatting for program details"""
    if len(full_text) <= max_length:
        return full_text
    
    # Check if we have structured content with DESCRIPTION and ADMISSION sections
    if "DESCRIPTION:" in full_text and "ADMISSION:" in full_text:
        # Extract both sections
        desc_part = ""
        admission_part = ""
        
        if " | " in full_text:
            parts = full_text.split(" | ")
            for part in parts:
                if part.startswith("DESCRIPTION:"):
                    desc_part = part.replace("DESCRIPTION:", "").strip()
                elif part.startswith("ADMISSION:"):
                    admission_part = part.replace("ADMISSION:", "").strip()
        else:
            # Try to extract from the text directly
            desc_match = re.search(r'DESCRIPTION:(.*?)(?=ADMISSION:|$)', full_text, re.DOTALL)
            admission_match = re.search(r'ADMISSION:(.*?)(?=DESCRIPTION:|$)', full_text, re.DOTALL)
            
            if desc_match:
                desc_part = desc_match.group(1).strip()
            if admission_match:
                admission_part = admission_match.group(1).strip()
        
        # Process DESCRIPTION part - extract key program information
        program_info = []
        
        # Extract PROGRAMME information
        programme_match = re.search(r'PROGRAMME[^A-Z]*([A-Z][^A-Z]{5,100})', desc_part, re.DOTALL)
        if programme_match:
            program_info.append(f"PROGRAMME: {programme_match.group(1).strip()}")
        
        # Extract SEMESTER information
        semester_match = re.search(r'SEMESTRE?[^A-Z]*(\d+\s*S?M?ESTERS?)', desc_part, re.IGNORECASE)
        if semester_match:
            program_info.append(f"SEMESTRE: {semester_match.group(1).strip()}")
        
        # Extract DURATION
        duration_match = re.search(r'DURATION[^A-Z]*(\d+\s*YEARS?)', desc_part, re.IGNORECASE)
        if not duration_match:
            duration_match = re.search(r'DURÉE[^A-Z]*(\d+\s*ANS?)', desc_part, re.IGNORECASE)
        if duration_match:
            program_info.append(f"DURATION: {duration_match.group(1).strip()}")
        
        # Extract CREDIT information
        credit_match = re.search(r'CREDIT[^A-Z]*(\d+)', desc_part, re.IGNORECASE)
        if credit_match:
            program_info.append(f"CREDIT: {credit_match.group(1).strip()}")
        
        # Extract PARTNER INSTITUTION
        partner_match = re.search(r'PARTNER INSTITUTION[^A-Z]*([A-Z][^A-Z]{5,100})', desc_part, re.DOTALL)
        if partner_match:
            program_info.append(f"PARTNER INSTITUTION: {partner_match.group(1).strip()}")
        
        # Extract ACCREDITATION
        accreditation_match = re.search(r'ACCREDITATION[^A-Z]*([A-Za-z][^A-Z]{5,100})', desc_part, re.DOTALL)
        if accreditation_match:
            program_info.append(f"ACCREDITATION: {accreditation_match.group(1).strip()}")
        else:
            program_info.append("ACCREDITATION: -")
        
        # Build structured description
        structured_desc = desc_part
        if program_info:
            # Add program info to description
            program_section = " ".join(program_info)
            structured_desc = f"{desc_part} {program_section}"
        
        # Process ADMISSION part - structure key sections
        structured_admission = admission_part
        
        # Extract STUDENT PROFILE section
        profile_match = re.search(r'(STUDENT PROFILE[^A-Z]*[A-Za-z].{20,300}?)(?=APPLICATION FILE|ADMISSION TEST|PROGRAMME|$)', admission_part, re.DOTALL | re.IGNORECASE)
        if profile_match:
            profile_text = profile_match.group(1).strip()
            structured_admission = profile_text
        
        # Extract APPLICATION FILE section
        file_match = re.search(r'(APPLICATION FILE[^A-Z]*[A-Za-z].{50,400}?)(?=STUDENT PROFILE|ADMISSION TEST|PROGRAMME|$)', admission_part, re.DOTALL | re.IGNORECASE)
        if file_match:
            file_text = file_match.group(1).strip()
            # Clean up the file items - replace bullets with semicolons
            file_text = re.sub(r'[-–]\s*', '; -', file_text)
            if structured_admission != admission_part:  # If we already have profile
                structured_admission += " " + file_text
            else:
                structured_admission = file_text
        
        # Build final structured content
        final_content = f"DESCRIPTION: {structured_desc} | ADMISSION: {structured_admission}"
        
        # Final length control
        if len(final_content) > max_length:
            # Truncate admission part first if needed
            admission_start = final_content.find("ADMISSION:")
            if admission_start > 0:
                desc_part_final = final_content[:admission_start].strip()
                admission_part_final = final_content[admission_start:]
                
                available_space = max_length - len(desc_part_final) - 5
                if available_space > 100:
                    admission_part_final = admission_part_final[:available_space-3] + "..."
                    final_content = f"{desc_part_final} {admission_part_final}"
                else:
                    # Keep description only if admission doesn't fit
                    final_content = desc_part_final[:max_length-3] + "..."
        
        return final_content
    
    # For content without clear structure, use simple truncation
    if len(full_text) > max_length:
        if '.' in full_text[:max_length-50]:
            last_dot = full_text[:max_length-50].rfind('.')
            if last_dot > max_length // 2:
                return full_text[:last_dot+1]
        
        return full_text[:max_length-3] + "..."
    
    return full_text



def extract_html_content(speciality_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and clean HTML content - ONLY DESCRIPTION FIELDS
    """
    # Define ONLY description fields (no admission fields)
    speciality_fields = [
        'zz_Speciality_HtmlOnlineDescription'
    ]
    
    parcours_fields = [
        'zz_Parcours_HtmlOnlineDescription'
    ]
    
    extracted_text = ''
    
    # Check which fields have content
    speciality_has_content = any(
        speciality_data.get(field) not in [None, '[null]', '', 'null'] 
        for field in speciality_fields
    )
    
    parcours_has_content = any(
        speciality_data.get(field) not in [None, '[null]', '', 'null'] 
        for field in parcours_fields
    )
    
    # Apply priority logic
    if speciality_has_content and not parcours_has_content:
        # Use only Speciality description fields
        for field in speciality_fields:
            if (speciality_data.get(field) not in [None, '[null]', '', 'null']):
                html_content = str(speciality_data[field])
                plain_text = re.sub(r'<[^>]*>', ' ', html_content)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                
                if plain_text and len(plain_text) > 10:
                    extracted_text += "DESCRIPTION: " + plain_text
    
    elif parcours_has_content and not speciality_has_content:
        # Use only Parcours description fields
        for field in parcours_fields:
            if (speciality_data.get(field) not in [None, '[null]', '', 'null']):
                html_content = str(speciality_data[field])
                plain_text = re.sub(r'<[^>]*>', ' ', html_content)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                
                if plain_text and len(plain_text) > 10:
                    extracted_text += "DESCRIPTION: " + plain_text
    
    elif speciality_has_content and parcours_has_content:
        # Use both Speciality and Parcours description fields
        all_fields = speciality_fields + parcours_fields
        for field in all_fields:
            if (speciality_data.get(field) not in [None, '[null]', '', 'null']):
                html_content = str(speciality_data[field])
                plain_text = re.sub(r'<[^>]*>', ' ', html_content)
                plain_text = re.sub(r'\s+', ' ', plain_text).strip()
                
                if plain_text and len(plain_text) > 10:
                    # If we already have content, add it with separator
                    if extracted_text:
                        extracted_text += " | " + plain_text
                    else:
                        extracted_text += "DESCRIPTION: " + plain_text
    
    # Summarize the content (your existing logic handles this)
    if extracted_text:
        # Only call summarize_speciality_content if content exceeds limit
        if len(extracted_text) <= 600:
            summarized_content = extracted_text
        else:
            summarized_content = summarize_speciality_content(extracted_text.strip(), max_length=600)
    else:
        # Fallback to basic description if no HTML content
        basic_desc = speciality_data.get('Speciality_Description', '') or speciality_data.get('Parcours_Name', '')
        summarized_content = basic_desc
    
    # Clean data structure
    clean_data = {
        'speciality_name': speciality_data.get('Speciality_Name'),
        'speciality_description': speciality_data.get('Speciality_Description'),
        'language': speciality_data.get('Speciality_Language'),
        'max_level': speciality_data.get('Speciality_Max_Level_Name'),
        'cycle_name': speciality_data.get('Cycle_Name'),
        'parcours_abreviation': speciality_data.get('Parcours_Abreviation'),
        'parcours_name': speciality_data.get('Parcours_Name'),
        'content': summarized_content,
    }
    
    # Remove empty fields
    clean_data = {k: v for k, v in clean_data.items() if v not in [None, '', '[null]', 'null']}
    
    return clean_data




#def clean_entrance_data(entrance_data: List[Dict]) -> List[Dict]:
    """Remove unnecessary fields from entrance endpoint"""
    cleaned = []
    for item in entrance_data:
        if isinstance(item, dict):
            # **KEEP ONLY THESE - REMOVE Entrance_Guid and others**
            cleaned_item = {
                'entrance_id': item.get('Entrance_ID'),
                'entrance_name': item.get('Entrance_Name'),
                'entrance_description': item.get('Entrance_Description'),
                # **REMOVED: Entrance_Guid, Ministry_ID, Year, SchoolID, etc.**
            }
            cleaned_item = {k: v for k, v in cleaned_item.items() if v not in [None, '', '[null]']}
            cleaned.append(cleaned_item)
    return cleaned

#def clean_sector_data(sector_data: List[Dict]) -> List[Dict]:
    """Remove unnecessary fields from sector endpoint"""
    cleaned = []
    for item in sector_data:
        if isinstance(item, dict):
            # **KEEP ONLY THESE - REMOVE Sector_Guid and others**
            cleaned_item = {
                'sector_id': item.get('Sector_ID'),
                'sector_name': item.get('Sector_Name'),
                #'sector_description': item.get('Sector_Description'),
                # **REMOVED: Sector_Guid, Ministry_ID, Year, SchoolID, etc.**
            }
            cleaned_item = {k: v for k, v in cleaned_item.items() if v not in [None, '', '[null]']}
            cleaned.append(cleaned_item)
    return cleaned

def process_speciality_data(api_data: Dict) -> Dict:
    """
    Process ALL endpoints: summarize specialities + clean others + remove STAFF items
    """
    processed_data = api_data.copy()
    
    # Process speciality endpoint
    if 'speciality/v1/LIST' in processed_data:
        specialities = processed_data['speciality/v1/LIST']
        processed_specialities = []
        staff_count = 0
        
        for speciality in specialities:
            if isinstance(speciality, dict):
                # Filter out items where Speciality_ID contains "STAFF"
                speciality_id = speciality.get('Speciality_ID', '')
                if speciality_id and 'STAFF' in str(speciality_id).upper():
                    staff_count += 1
                    continue  # Skip this item
                processed_specialities.append(extract_html_content(speciality))
        
        api_data['speciality/v1/LIST'] = processed_specialities
        print(f"✅ Removed {staff_count} items containing 'STAFF' in Speciality_ID")
    
    #if 'sector/v1/LIST' in processed_data:
      #  api_data['sector/v1/LIST'] = clean_sector_data(processed_data['sector/v1/LIST'])
    
    return api_data


# ======================
# API DATA FETCHING (UNCHANGED)
# ======================
API_BASE_URL = "https://iuc-api-aca.bitang.net/api"
ApiKey = "iuc3783XX19ezUNRD884296Pc" 

API_ENDPOINTS = [
    #"entrance/v1/LIST",
 #   "sector/v1/LIST", 
    "speciality/v1/LIST"
]

API_PARAMS = {
   # "entrance/v1/LIST": {"Year": "2024-2025", "SchoolID": "IUC"},
 #   "sector/v1/LIST": {"Year": "2024-2025", "SchoolID": "IUC"},
    "speciality/v1/LIST": {"Year": "2024-2025", "SchoolID": "IUC"}
}

async def fetch_api_data():
    async with httpx.AsyncClient() as client:
        data = {}
        headers = {"Authorization": f"Bearer {ApiKey}"}
        for endpoint in API_ENDPOINTS:
            params = API_PARAMS.get(endpoint.strip(), {})
            params["ApiKey"] = ApiKey
            
            for attempt in range(3):
                try:
                    resp = await client.get(f"{API_BASE_URL}/{endpoint.strip()}", 
                                          headers=headers, 
                                          params=params)
                    if resp.status_code == 200:
                        data[endpoint] = resp.json()
                        break
                    else:
                        print(f"API error {resp.status_code} for {endpoint}: {resp.text}")
                except Exception as e:
                    if attempt == 2:
                        print(f"API error for {endpoint}: {e}")
                        data[endpoint] = []
        return data

# ======================
# GLOBAL STATE / CACHE (MODIFIED)
# ======================
context_cache = {
    "data": None,
    "timestamp": None,
    "lock": asyncio.Lock()
}

async def get_cached_context():
    async with context_cache["lock"]:
        now = datetime.now()
        if not context_cache["data"] or (context_cache["timestamp"] is None) or (now - context_cache["timestamp"]).seconds > CACHE_TTL:
            # Fetch raw data from all endpoints
            raw_data = await fetch_api_data()
            # Process ONLY the speciality endpoint
            context_cache["data"] = process_speciality_data(raw_data)
            context_cache["timestamp"] = now
        return context_cache["data"]


# ======================
# ADDITIONAL ENDPOINTS FOR DEBUGGING
# ======================

@app.get("/api/raw-data")
async def get_raw_data():
    """Get raw unprocessed data from all endpoints"""
    data = await fetch_api_data()
    return data

@app.get("/api/processed-data")
async def get_processed_data():
    """Get processed data (specialities cleaned)"""
    data = await get_cached_context()
    return data

@app.get("/api/specialities")
async def get_specialities():
    """Get only processed specialities"""
    data = await get_cached_context()
    return {
        "specialities": data.get('speciality/v1/LIST', []),
        "count": len(data.get('speciality/v1/LIST', []))
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "last_api_fetch": context_cache.get("timestamp", None),
        "endpoints_loaded": list((await get_cached_context()).keys()) if context_cache["data"] else []
    }

@app.get("/api/context")
@cache(expire=300)
async def get_context_data():
    """Endpoint to get the cached API data for n8n"""
    try:
        context_data = await get_cached_context()
        return {
            "status": "success",
            "data": context_data,
            "message": "Speciality descriptions are pre-summarized to reduce token usage",
            "timestamp": context_cache["timestamp"].isoformat() if context_cache["timestamp"] else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
