import feedparser
import os
from datetime import datetime
import re
import requests
import json
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
        resp = requests.get(article_url, headers=headers, timeout=10)
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
        return ""
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
        "model": "llama-3.1-8b-instant",  # fast, free-tier Groq model; swap for "llama-3.3-70b-versatile" for higher quality
        "max_tokens": 120,
        "temperature": 0.7,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Groq API error: {e}")
        return ""

def fetch_and_save_techcrunch_articles():
    FEED_URL = 'https://techcrunch.com/feed/'
    SAVE_DIR = 'data/summaries/'
    os.makedirs(SAVE_DIR, exist_ok=True)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    response = requests.get(FEED_URL, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch feed: {response.status_code}")
        return
    feed = feedparser.parse(response.content)
    print(f"Fetched {len(feed.entries)} entries from TechCrunch RSS feed.")
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        summary = entry.summary if hasattr(entry, 'summary') else ''
        published = entry.published if hasattr(entry, 'published') else ''
        image_url = extract_image_url(entry)
        llm_summary = get_llm_summary_groq(title, summary)
        date_str = ''
        if published:
            try:
                date_obj = datetime(*entry.published_parsed[:6])
                date_str = date_obj.strftime('%Y-%m-%d')
            except Exception:
                date_str = ''
        filename_base = f"{date_str}-{slugify(title)[:50]}"
        # Save markdown as before, now with LLM summary
        md_filepath = os.path.join(SAVE_DIR, f"{filename_base}.md")
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"**Published:** {published}\n\n")
            f.write(f"**Link:** [{link}]({link})\n\n")
            f.write(f"**LLM Summary:** {llm_summary}\n\n")
            f.write(f"{summary}\n")
        # Save JSON with metadata
        json_filepath = os.path.join(SAVE_DIR, f"{filename_base}.json")
        with open(json_filepath, 'w', encoding='utf-8') as jf:
            json.dump({
                'title': title,
                'link': link,
                'summary': summary,
                'published': published,
                'image_url': image_url,
                'llm_summary': llm_summary
            }, jf, ensure_ascii=False, indent=2)
    print("Done writing articles.")

if __name__ == "__main__":
    fetch_and_save_techcrunch_articles()