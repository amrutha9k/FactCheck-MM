import os
import json
import requests
import re
import time
import logging
import tempfile
import mimetypes
import base64
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
import trafilatura
from sentence_transformers import util
from serpapi import GoogleSearch
from openai import OpenAI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

# UPDATED JUNK LIST 
JUNK_IMAGE_KEYWORDS = [
    'placeholder', 'logo', 'icon', 'avatar', 'profile', 'spinner', 
    'loading', 'default', 'advert', 'banner', 'thumbnail', 'widget',
    'social', 'share', 'subscribe', 'follow', 'whatsapp', 'telegram', 'channel',
    'header', 'footer', 'overlay', 'button', 'nav', 'menu', 'home',
    'category', 'tag', 'slide', 'homeboom', 'non-boom', 'careers', 'category-icon',
    'google-news', 'symbol', 'graphic'
]

logging.basicConfig(filename='pipeline.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_robust_session():
    session = requests.Session()
    retry = Retry(total=3, read=3, connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

http = get_robust_session()

def setup_openai():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: OPENAI_API_KEY not set.")
    return OpenAI(api_key=api_key)

def normalize_url(url):
    """
    Strict URL normalization for duplicate detection and exclusion.
    """
    if not url:
        return ""
    
    u = unquote(str(url)).lower().strip()
    u = re.sub(r'^[a-z]+://', '', u)
    u = re.sub(r'^www\d*\.', '', u)
    u = re.sub(r'^m\.', '', u)
    u = re.sub(r'^mobile\.', '', u)
    u = re.sub(r':\d+', '', u)
    u = u.split('?')[0]
    u = u.split('#')[0]
    u = u.rstrip('/')
    u = re.sub(r'/index\.(html?|php|asp|aspx|jsp)$', '', u)
    u = re.sub(r'/+', '/', u)
    u = u.strip()
    
    return u

def get_domain(url):
    """Extract base domain from URL for domain-level blocking"""
    normalized = normalize_url(url)
    if not normalized:
        return ""
    # Get everything before the first slash (the domain)
    domain = normalized.split('/')[0]
    return domain

# --- 1. ROBUST SEARCH FUNCTION ---
def perform_search(query, num_results=5):
    results_list = []
    
    # 1. Try SerpApi
    serp_key = os.environ.get("SERPAPI_KEY")
    if serp_key:
        try:
            search = GoogleSearch({"q": query, "api_key": serp_key, "gl": "in", "num": num_results})
            data = search.get_dict()
            
            # Check if SerpApi returned an error (e.g., quota exhausted)
            if 'error' in data:
                logging.error(f"SerpApi Error Response: {data['error']}")
            
            elif 'organic_results' in data:
                for item in data['organic_results']:
                    results_list.append({
                        "link": item.get('link'), 
                        "title": item.get('title')
                    })
            
            # CRITICAL FIX: Only return here if we actually got results.
            # If results_list is empty, we MUST fall through to the next method.
            if results_list:
                return results_list
                
        except Exception as e:
            logging.error(f"SerpApi Exception: {e}")
            # Do not return; let it fall through to CSE

    # 2. Try Google Custom Search (CSE) Fallback
    print("   [Info] Falling back to Google Custom Search...")
    google_key = os.environ.get("GOOGLE_SEARCH_KEY")
    google_cx = os.environ.get("GOOGLE_CX")
    
    if google_key and google_cx:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {'key': google_key, 'cx': google_cx, 'q': query, 'num': num_results}
            resp = http.get(url, params=params).json()
            
            if 'error' in resp:
                 logging.error(f"Google CSE Error: {resp['error']}")
            
            elif 'items' in resp:
                for item in resp['items']:
                    results_list.append({
                        "link": item.get('link'), 
                        "title": item.get('title')
                    })
            return results_list
        except Exception as e:
            logging.error(f"Google CSE Failed: {e}")

    return results_list

# --- 2. DOWNLOADER ---
def download_image(url, referer_url=None):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': referer_url if referer_url else 'https://www.google.com'
        }
        r = http.get(url, headers=headers, stream=True, timeout=8)
        
        if r.status_code == 200:
            if len(r.content) < 1024: return None 

            content_type = r.headers.get('content-type', '').lower()
            if 'image' not in content_type or 'svg' in content_type: return None

            ext = mimetypes.guess_extension(content_type) or ".jpg"
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tfile.write(r.content)
            tfile.close()
            return tfile.name
    except:
        pass
    return None

# --- 3. SUMMARIZER ---
def summarize_text(text, client):
    if len(text) < 6000:
        return text
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a research assistant. Summarize this news article. Preserve direct quotes, dates, fact-check rulings, and key evidence. Max 4000 characters."},
                {"role": "user", "content": text[:15000]}
            ]
        )
        return "SUMMARY: " + response.choices[0].message.content
    except Exception as e:
        return text[:6000]

# --- 4. CONTEXT EXTRACTOR ---
def extract_image_context(img_tag):
    parts = []
    alt = img_tag.get('alt', '').strip()
    if len(alt) > 5: parts.append(alt)
    
    title = img_tag.get('title', '').strip()
    if len(title) > 5: parts.append(title)

    parent = img_tag.parent
    for _ in range(3):
        if not parent: break
        caption = parent.find('figcaption')
        if caption:
            parts.append(caption.get_text(strip=True))
            break
        parent = parent.parent
    
    container = img_tag.find_parent(['div', 'figure', 'article', 'p'])
    if container:
        prev = container.find_previous('p')
        if prev: parts.append(prev.get_text(strip=True)[:300])
        nxt = container.find_next('p')
        if nxt: parts.append(nxt.get_text(strip=True)[:300])

    return " ".join(parts).strip()

# --- 5. QUERY GENERATION ---
def generate_search_queries(claim, client, input_image_path=None):
    visual_instruction = "4. Since the user provided an image, include descriptive keywords of visual elements." if input_image_path else "4. Focus ONLY on text facts."

    system_prompt = f"""You are a linguistic expert fact-checker and search strategist.
Supported Languages: [English, Hindi, Telugu, Tamil, Kannada, Malayalam, Punjabi, Bengali, Gujarati, Assamese, Odia, Marathi, Urdu].

### LEARNING FROM EXAMPLES (DO NOT REPEAT MISTAKES)

--- SUCCESS CASE (Specific Text / Slogan) ---
    User Claim: "देश जुमलों से नही चलेगा प्रधानमंत्री राहुल गांधी बनेगा” स्लोगन वाली ऑटो की तस्वीर वायरल हुई"
    Why it worked: The queries focused on the exact slogan text.
    Good Queries:
    - "देश जुमलों से नही चलेगा प्रधानमंत्री राहुल गांधी बनेगा fact check"
    - "Rahul Gandhi auto rickshaw slogan viral true or false"
    - "देश जुमलों से नही चलेगा photo real vs fake"

    --- FAILURE CASE (Identity/Context Missed) ---
    User Claim: "অসমৰ মুখ্যমন্ত্ৰী হিমন্ত বিশ্ব শৰ্মা বুলি দাবী কৰা এজন ব্যক্তিৰ ভিডিঅ’ ভাইৰেল হৈছে"
    (Translation: A video of a person claiming to be Assam CM Himanta Biswa Sarma is viral)
    
    BAD Queries (These Failed):
    1. "হিমন্ত বিশ্ব শৰ্মাৰ ভিডিঅ’ ভাইৰেল হৈছে নেকি?" (Is Himanta's video viral? -> Too generic, returns real news)
    2. "হিমন্ত বিশ্ব শৰ্মাৰ নতুন ভিডিঅ’" (Himanta's new video -> Wrong intent)
    3. "Himanta Biswa Sarma viral video" (Returns general news)

    CORRECTED STRATEGY: The claim implies an IMPOSTER, LOOKALIKE, or FALSE IDENTITY.
    
    GOOD Queries (Native Assamese):
    1. "হিমন্ত বিশ্ব শৰ্মাৰ দৰে দেখিবলৈ মানুহজনৰ ভাইৰেল ভিডিঅ'ৰ সত্যতা" (Truth of video of person looking like Himanta)
    2. "অসমৰ মুখ্যমন্ত্ৰী বুলি দাবী কৰা ব্যক্তিৰ আচল পৰিচয়" (Real identity of person claiming to be CM)
    3. "হিমন্ত বিশ্ব শৰ্মাৰ নকল ভিডিঅ' ফেক্ট চেক" (Himanta Biswa Sarma fake/copy video fact check)
    
    GOOD Queries (English):
    4. "Himanta Biswa Sarma lookalike viral video fact check"
    5. "Person claiming to be Assam CM viral video truth"


### YOUR TASK:
Generate a JSON object {{'queries': [...]}}.
Rules:
-Analyze the User Claim.
-If it involves a famous person, determine the SPECIFIC contention (Deepfake? Lookalike? Old Video? Slogan?).
- Keep queries SHORT but do not cut off important context.
- If the claim involves a famous person, determine the SPECIFIC contention (Deepfake? Lookalike? Old Video? Slogan?).
- Do NOT generate generic "Viral Video" queries for famous people.
- Extract KEY ENTITIES (names, places, events) but donot cutt off important information and keep the queries as short as possible

1. Detect the language of the claim.
2. Generate 2 key word based queries in the DETECTED LANGUAGE (Native).
3. Generate 1 key word based query in ENGLISH (Translated).

{visual_instruction}

Output Format (JSON only):
{{
    "queries": [
        "native language query 1",
        "native language query 2",
        "English query 1",
    ]
}}

No explanations. Just JSON."""

    messages = [{"role": "system", "content": system_prompt}]
    
    user_content = []
    if input_image_path:
        with open(input_image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        user_content.append({"type": "text", "text": f"CLAIM: {claim}"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    else:
        user_content.append({"type": "text", "text": f"CLAIM: {claim}"})

    messages.append({"role": "user", "content": user_content})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get("queries", [])
    except:
        return [claim + " fact check"]

# --- 6. MAIN LOGIC ---
def verify_row(row, embed_model, client):
    claim = row.get('claim', '')
    source_url = row.get('url', '')
    user_image_src = row.get('image_src', '')

    # 1. Download User Image
    local_input_img = None
    if str(user_image_src).startswith('http'):
        local_input_img = download_image(user_image_src)

    # 2. Queries
    queries = generate_search_queries(claim, client, local_input_img)
    print(f"Queries: {queries}")

    # 3. Search & Scrape
    # 3. Search & Scrape with Domain-Level Exclusion
    seen_urls = set()
    excluded_domains = set()
    
    # --- STRICT SOURCE EXCLUSION SETUP ---
    clean_source_url = normalize_url(source_url)
    if clean_source_url:
        seen_urls.add(clean_source_url)
        source_domain = get_domain(source_url)
        if source_domain:
            excluded_domains.add(source_domain)
            print(f" Excluding entire domain: {source_domain}")

    articles_data = []
    
    for q in queries:
        results = perform_search(q, num_results=5)
        
        for item in results:
            url = item.get('link')
            title = item.get('title', '')
            
            if not url:
                continue
            
            # --- DOMAIN-LEVEL CHECK FIRST ---
            url_domain = get_domain(url)
            if url_domain in excluded_domains:
                print(f"SKIPPED (source domain): {url}")
                continue
            
            # --- EXACT URL CHECK ---
            clean_found_url = normalize_url(url)
            if clean_found_url in seen_urls:
                print(f" SKIPPED (duplicate): {url}")
                continue
            
            seen_urls.add(clean_found_url)

            try:
                downloaded = trafilatura.fetch_url(url)
                if not downloaded: continue
                text = trafilatura.extract(downloaded)
                if not text: continue

                # Image Extraction
                soup = BeautifulSoup(downloaded, 'html.parser')
                page_images = []
                seen_img_urls = set()

                # Meta Image
                meta_img = soup.find("meta", property="og:image") or soup.find("meta", property="twitter:image")
                if meta_img and meta_img.get("content"):
                    full_meta_url = urljoin(url, meta_img.get("content").strip())
                    if not any(junk in full_meta_url.lower() for junk in JUNK_IMAGE_KEYWORDS):
                        page_images.append({
                            "url": full_meta_url,
                            "context": f"LEAD IMAGE for Article: {title}. Main visual evidence.",
                            "type": "meta"
                        })
                        seen_img_urls.add(full_meta_url)

                # Body Images
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src')
                    if not src: continue
                    real_url = urljoin(url, src)
                    if real_url in seen_img_urls: continue
                    if any(junk in real_url.lower() for junk in JUNK_IMAGE_KEYWORDS): continue
                    
                    ctx = extract_image_context(img)
                    if len(ctx) > 15:
                        page_images.append({"url": real_url, "context": ctx, "type": "body"})
                        seen_img_urls.add(real_url)
                
                articles_data.append({"url": url, "text": text, "images": page_images})
            except Exception as e:
                logging.error(f"Scrape error on {url}: {e}")
                continue

    if not articles_data:
        return {"verdict": "Unverified", "explanation_english": "No evidence found."}

    # 4. RANKING (SUPPRESSED PROGRESS BARS)
    claim_vec = embed_model.encode(claim, show_progress_bar=False)
    
    # Text Ranking
    for art in articles_data:
        art['score'] = util.cos_sim(claim_vec, embed_model.encode(art['text'][:8000], show_progress_bar=False)).item()
    
    articles_data.sort(key=lambda x: x['score'], reverse=True)
    top_5_articles = articles_data[:5]
    top_3_subset = articles_data[:3] # We only pick images from these 3

    # --- NEW IMAGE SELECTION LOGIC (Top 1 from each of Top 3 Articles) ---
    top_3_images = []
    
    for art in top_3_subset:
        # 1. Rank all images inside this specific article
        art_images = art['images']
        if not art_images: continue
        
        for img in art_images:
            # Score this image against the claim
            base_score = util.cos_sim(claim_vec, embed_model.encode(img['context'], show_progress_bar=False)).item()
            if img.get('type') == 'meta': base_score += 0.05
            img['score'] = base_score
            
        # 2. Filter garbage and Sort
        valid_imgs = [i for i in art_images if i['score'] > 0.32] # Increased threshold
        valid_imgs.sort(key=lambda x: x['score'], reverse=True)
        
        # 3. Pick ONLY the single best image from this article
        if valid_imgs:
            top_3_images.append(valid_imgs[0])

    # 5. PREPARE PAYLOAD
    evidence_img_paths = []
    top_img_urls = []
    for img in top_3_images:
        path = download_image(img['url'])
        if path:
            evidence_img_paths.append({"path": path, "context": img['context']})
            top_img_urls.append(img['url'])

    content = [{"type": "text", "text": f"USER CLAIM: {claim}\n\n"}]

    for i, art in enumerate(top_5_articles):
        clean_text = summarize_text(art['text'], client)
        content.append({"type": "text", "text": f"=== SOURCE {i+1}: {art['url']} ===\n{clean_text}\n\n"})

    if local_input_img:
        with open(local_input_img, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        content.append({"type": "text", "text": "=== USER SUBMITTED IMAGE ==="})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    for i, img in enumerate(evidence_img_paths):
        with open(img['path'], "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        content.append({"type": "text", "text": f"=== EVIDENCE IMAGE {i+1} (Context: {img['context']}) ==="})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    # 6. VERDICT
    system_prompt_verdict = """You are a professional fact-checker. Analyze the evidence and verify the claim.
CRITICAL INSTRUCTIONS:
1. Read ALL the evidence carefully
2. Check if sources explicitly mention the claim as "fake", "edited", "false", "misleading", or "old"
3. Compare images if provided - look for signs of manipulation
4. Base your verdict ONLY on the evidence provided
5. Quote specific sources when explaining your verdict

OUTPUT FORMAT (strict JSON):
{
    "verdict": "True / False / Misleading / Unverified",
    "explanation_native": "Explain in the original language.",
    "corrected_claim_native": "Correct facts in original language.",
    "claim_english": "Translate claim to english",
    "explanation_english": "Translate explanation to English",
    "corrected_claim_english": "Translate correction to English"
}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt_verdict}, {"role": "user", "content": content}],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
    except Exception as e:
        result = {"verdict": "Error", "explanation_english": str(e)}

    # Cleanup
    if local_input_img and os.path.exists(local_input_img): os.remove(local_input_img)
    for img in evidence_img_paths:
        if os.path.exists(img['path']): os.remove(img['path'])

    # Metadata & Queries
    result['top_3_article_urls'] = json.dumps([a['url'] for a in top_5_articles[:3]])
    result['top_3_image_urls'] = json.dumps(top_img_urls)
    result['generated_queries'] = json.dumps(queries) 

    return result