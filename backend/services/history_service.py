import os
import json
from datetime import datetime, timezone, timedelta
import requests

# Local IST Timezone
IST_TZ = timezone(timedelta(hours=5, minutes=30))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_CACHE_DIR = os.path.join(BASE_DIR, 'data', 'history')

# Comprehensive Perpetual Tech History Milestones Bank (365-Day Fallback & Core Knowledge)
PERPETUAL_TECH_HISTORY = {
    "09-05": [
        {
            "year": "1977",
            "title": "NASA Launches Voyager 1 Space Probe",
            "fact": "Equipped with the iconic Golden Record and cutting-edge 1970s digital computers, Voyager 1 launched to explore interstellar space. Today, it remains the farthest human-made object in the cosmos."
        },
        {
            "year": "2008",
            "title": "Google Releases Chrome Beta 0.2",
            "fact": "Google unveiled the first public beta of the Chrome browser, introducing the revolutionary V8 JavaScript engine that transformed web application performance forever."
        },
        {
            "year": "1997",
            "title": "Google.com Domain Registered",
            "fact": "Larry Page and Sergey Brin officially registered the domain Google.com, paving the way for modern algorithmic search and digital indexing."
        }
    ],
    "09-06": [
        {
            "year": "1991",
            "title": "Tim Berners-Lee Posts First WWW Summary",
            "fact": "Tim Berners-Lee publicly posted the first summary of the World Wide Web project on the alt.hypertext newsgroup, officially inviting global developers to join the Web."
        },
        {
            "year": "1978",
            "title": "First Production 64KB RAM Chip",
            "fact": "IBM researchers unveiled the industry's first working 64-kilobit dynamic RAM chip, dramatically multiplying computer memory capacity."
        }
    ],
    "09-07": [
        {
            "year": "1998",
            "title": "Google Formally Incorporated",
            "fact": "Google was officially incorporated as a private company in Menlo Park, California, with initial funding from Sun Microsystems co-founder Andy Bechtolsheim."
        },
        {
            "year": "2005",
            "title": "Apple Unveils iPod Nano & ROKR Phone",
            "fact": "Steve Jobs introduced the ultra-thin iPod Nano and the Motorola ROKR, Apple's first precursor step into mobile telephony before the iPhone."
        }
    ],
    "09-08": [
        {
            "year": "1930",
            "title": "Invention of Scotch Tape for Tech Storage",
            "fact": "3M engineer Richard Drew invented transparent cellophane tape, which later became instrumental in sealing early magnetic tapes and circuit prototypes."
        },
        {
            "year": "1966",
            "title": "Star Trek Premieres Inspiring Tech Pioneers",
            "fact": "Star Trek debuted on television, inspiring generations of engineers who later invented flip phones, tablet computers, and voice interfaces."
        }
    ],
    "09-09": [
        {
            "year": "1947",
            "title": "First Actual Computer 'Bug' Found",
            "fact": "Grace Hopper's team at Harvard University found a real moth trapped in Relay #70 of the Mark II computer, coining the famous term 'debugging'."
        },
        {
            "year": "2014",
            "title": "Apple Introduces Apple Watch & iPhone 6",
            "fact": "Apple entered the wearable computing industry with the original Apple Watch and introduced Apple Pay for contactless NFC payments."
        }
    ],
    "09-10": [
        {
            "year": "2008",
            "title": "Large Hadron Collider Powered On",
            "fact": "CERN activated the Large Hadron Collider, establishing a massive distributed grid computing network for particle physics analysis."
        },
        {
            "year": "2019",
            "title": "Apple Announces A13 Bionic Neural Engine",
            "fact": "Apple unveiled the A13 Bionic chip featuring 8.5 billion transistors, accelerating on-device machine learning for mobile devices."
        }
    ]
}

# Default universal milestones for any unmapped day
DEFAULT_MILESTONES = [
    {
        "year": "1969",
        "title": "ARPANET Pioneer Node Activated",
        "fact": "The first host-to-host message was transmitted across ARPANET between UCLA and Stanford, establishing the foundation of the modern Internet."
    },
    {
        "year": "1991",
        "title": "Linus Torvalds Announces Linux Kernel",
        "fact": "Linus Torvalds released the initial Linux kernel 0.01, creating the open-source operating system that now powers the majority of global cloud servers."
    },
    {
        "year": "2007",
        "title": "Steve Jobs Unveils the Original iPhone",
        "fact": "Apple announced the iPhone, combining a widescreen iPod, a revolutionary mobile phone, and a breakthrough internet communicator into a single multitouch device."
    },
    {
        "year": "2022",
        "title": "OpenAI Launches ChatGPT",
        "fact": "OpenAI launched ChatGPT, sparking the generative AI revolution and making large language models accessible to hundreds of millions worldwide."
    }
]

class HistoryService:
    def __init__(self):
        os.makedirs(HISTORY_CACHE_DIR, exist_ok=True)

    def get_today_history(self) -> dict:
        """Fetch today's tech history milestones from cache, AI, or perpetual bank"""
        now = datetime.now(IST_TZ)
        date_key = now.strftime("%m-%d")
        cache_file = os.path.join(HISTORY_CACHE_DIR, f"{date_key}.json")

        # 1. Check local disk cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data and isinstance(data.get('milestones'), list) and len(data['milestones']) > 0:
                        return data
            except Exception:
                pass

        # 2. Check Perpetual Bank
        milestones = PERPETUAL_TECH_HISTORY.get(date_key)

        # 3. If missing or enrichment desired, query Groq AI
        if not milestones:
            ai_milestones = self.fetch_ai_milestones(now.strftime("%B %d"))
            if ai_milestones:
                milestones = ai_milestones
            else:
                milestones = DEFAULT_MILESTONES

        result = {
            "date": now.strftime("%d %B %Y"),
            "day": now.strftime("%A"),
            "date_key": date_key,
            "milestones": milestones
        }

        # Cache to disk for instant zero-latency future hits
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return result

    def fetch_ai_milestones(self, date_string: str) -> list:
        """Ask Groq LLM for 2-3 historical tech breakthroughs for a given date"""
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")
        if not api_key:
            return None

        prompt = (
            f"Provide 2-3 significant historical computing, internet, software, or tech hardware milestones that occurred on {date_string}.\n"
            "Return ONLY a valid JSON array of objects with keys: 'year', 'title', 'fact'.\n"
            "Keep each fact to 2 concise, fascinating sentences."
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "openai/gpt-oss-120b",
            "max_tokens": 350,
            "temperature": 0.5,
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                # Clean markdown json code blocks if present
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                data = json.loads(raw.strip())
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"AI history milestone note: {e}")

        return None

history_service = HistoryService()
