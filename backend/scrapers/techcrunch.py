import feedparser
import os
from datetime import datetime
import re
import requests
import json
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def extract_image_url(entry):
    # 1. Try media_content
    if 'media_content' in entry and entry.media_content:
        url = entry.media_content[0].get('url')
        if url:
            return url
    # 2. Try media_thumbnail
    if 'media_thumbnail' in entry and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url')
        if url:
            return url
    # 3. Try to extract from summary or content
    html_sources = []
    if hasattr(entry, 'summary'):
        html_sources.append(entry.summary)
    if hasattr(entry, 'content') and entry.content:
        html_sources.append(entry.content[0].value)
    for html in html_sources:
        match = re.search(r'<img[^>]+src="([^"]+)"', html)
        if match:
            return match.group(1)
    # 4. Scrape the article page for og:image or first <img>
    try:
        article_url = entry.link
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        resp = requests.get(article_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            # Try og:image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']
            # Fallback: first <img>
            first_img = soup.find('img')
            if first_img and first_img.get('src'):
                return first_img['src']
    except Exception as e:
        print(f"Error scraping image from {entry.link}: {e}")
    return ''

def get_llm_summary_groq(title, summary, audience="general tech audience"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY not set. Skipping LLM summarization.")
        return summary[:200] if summary else title

    prompt = (
        f"Article title: {title}\n"
        f"Article summary: {summary}\n\n"
        f"Summarize the above for a {audience} in 2-3 sentences."
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-120b",
        "max_tokens": 120,
        "temperature": 0.7,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    # Try up to 2 times with backoff on rate limits (429)
    for attempt in range(2):
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            )
            if response.status_code == 429:
                print("[GROQ RATE LIMIT] 429 received. Backing off for 2s...")
                time.sleep(2)
                continue
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
            else:
                print(f"Groq API fallback for '{title[:30]}...': {e}")
                
    # Fallback to cleaning HTML from summary snippet if LLM rate limited
    clean_summary = re.sub(r'<[^>]+>', '', summary).strip()
    return clean_summary[:200] + "..." if len(clean_summary) > 200 else clean_summary

from difflib import SequenceMatcher

STOPWORDS = {
    'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'for', 'to', 'of', 'in',
    'with', 'by', 'as', 'from', 'that', 'this', 'it', 'are', 'be', 'was', 'were', 'has',
    'had', 'have', 'but', 'not', 'if', 'then', 'so', 'do', 'does', 'did', 'can', 'will',
    'just', 'about', 'into', 'over', 'after', 'before', 'more', 'less', 'than', 'up',
    'out', 'off', 'no', 'yes', 'you', 'new', 'says', 'how', 'why', 'what', 'first',
    'here', 'now', 'its', 'itself', 'all', 'any', 'both', 'each', 'few', 'most', 'other',
    'some', 'such', 'only', 'own', 'same', 'too', 'very', 'announced', 'announces', 'launches', 'unveils'
}

def clean_title_tokens(title: str) -> set:
    """Extract clean content keywords from headline"""
    words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', title.lower())
    return set(w for w in words if w not in STOPWORDS)

def is_duplicate_headline(new_title: str, existing_titles: list, jaccard_thresh=0.48, seq_thresh=0.62):
    """
    Check if new_title is a duplicate of any title in existing_titles.
    Uses Token Jaccard Overlap and Levenshtein Sequence Ratio.
    """
    new_tokens = clean_title_tokens(new_title)
    if not new_tokens:
        return False, None
        
    for existing_title in existing_titles:
        existing_tokens = clean_title_tokens(existing_title)
        if not existing_tokens:
            continue
            
        intersection = len(new_tokens & existing_tokens)
        union = len(new_tokens | existing_tokens)
        jaccard = intersection / union if union > 0 else 0
        seq_ratio = SequenceMatcher(None, new_title.lower(), existing_title.lower()).ratio()
        
        # Match if either strong token overlap or high sequence ratio
        if (jaccard >= jaccard_thresh and intersection >= 3) or seq_ratio >= seq_thresh:
            return True, existing_title
            
    return False, None

FEEDS = [
    {'name': 'TechCrunch', 'url': 'https://techcrunch.com/feed/'},
    {'name': 'The Verge', 'url': 'https://www.theverge.com/rss/index.xml'},
    {'name': 'Wired', 'url': 'https://www.wired.com/feed/rss'},
    {'name': 'Ars Technica', 'url': 'https://feeds.arstechnica.com/arstechnica/index'}
]

def fetch_and_save_all_sources():
    SAVE_DIR = 'data/summaries/'
    os.makedirs(SAVE_DIR, exist_ok=True)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    total_new_articles = 0
    total_duplicates_skipped = 0
    
    # Load recent titles from disk (last 48h) for cross-feed deduplication
    existing_titles = []
    if os.path.exists(SAVE_DIR):
        for fname in sorted(os.listdir(SAVE_DIR), reverse=True)[:150]:
            if fname.endswith('.json'):
                try:
                    with open(os.path.join(SAVE_DIR, fname), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data.get('title'):
                            existing_titles.append(data['title'])
                except Exception:
                    pass
    
    for feed_info in FEEDS:
        source_name = feed_info['name']
        feed_url = feed_info['url']
        
        try:
            response = requests.get(feed_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"[{source_name}] Failed to fetch feed: {response.status_code}")
                continue
                
            feed = feedparser.parse(response.content)
            print(f"Fetched {len(feed.entries)} entries from {source_name} RSS feed.")
            
            for entry in feed.entries[:8]:  # Process top 8 entries per source
                title = entry.title
                link = entry.link
                summary = entry.summary if hasattr(entry, 'summary') else ''
                published = entry.published if hasattr(entry, 'published') else (entry.updated if hasattr(entry, 'updated') else '')
                
                date_str = ''
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        date_obj = datetime(*entry.published_parsed[:6])
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except Exception:
                        date_str = datetime.now().strftime('%Y-%m-%d')
                else:
                    date_str = datetime.now().strftime('%Y-%m-%d')

                filename_base = f"{date_str}-{slugify(source_name)}-{slugify(title)[:45]}"
                json_filepath = os.path.join(SAVE_DIR, f"{filename_base}.json")
                
                # Check exact file match
                if os.path.exists(json_filepath):
                    continue
                
                # Check cross-publisher duplicate headline
                is_dup, matched_title = is_duplicate_headline(title, existing_titles)
                if is_dup:
                    print(f"[{source_name}] 🚫 Skipped redundant cross-publisher story: '{title[:45]}...' (matches: '{matched_title[:45]}...')")
                    total_duplicates_skipped += 1
                    continue
                    
                image_url = extract_image_url(entry)
                llm_summary = get_llm_summary_groq(title, summary)
                time.sleep(0.5)
                
                with open(json_filepath, 'w', encoding='utf-8') as jf:
                    json.dump({
                        'title': title,
                        'link': link,
                        'summary': summary,
                        'published': published,
                        'image_url': image_url,
                        'llm_summary': llm_summary,
                        'source': source_name
                    }, jf, ensure_ascii=False, indent=2)
                    
                existing_titles.append(title)
                total_new_articles += 1
        except Exception as e:
            print(f"Error scraping {source_name}: {e}")
            
    print(f"Multi-source scraping complete. Added {total_new_articles} unique stories (Skipped {total_duplicates_skipped} redundant duplicates).")

def fetch_and_save_techcrunch_articles():
    fetch_and_save_all_sources()

if __name__ == "__main__":
    fetch_and_save_all_sources()