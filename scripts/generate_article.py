#!/usr/bin/env python3
"""
EasyEquity Article Bot — Gemini Edition (100% Free)
Runs daily via GitHub Actions.
Uses Google Gemini API (free tier) + Serper (free tier) for live news.
"""

import os
import sys
import json
import re
import time
import datetime
import requests
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
# Free Gemini model — no cost, no credit card needed
GEMINI_MODEL   = "gemini-2.0-flash-lite"
TODAY          = datetime.date.today().strftime("%b %d, %Y")
SLUG_DATE      = datetime.date.today().strftime("%Y-%m-%d")

# Rotates topic automatically every day
TOPIC_ROTATION = [
    "global trade tariffs and impact on markets",
    "Federal Reserve interest rate policy outlook",
    "emerging markets currency moves and economy",
    "US stock market earnings and valuations",
    "geopolitics oil gold and commodity prices",
    "China economy and global supply chains",
    "inflation consumer spending and economic data",
]
day_of_year = datetime.date.today().timetuple().tm_yday
TOPIC = os.environ.get("CUSTOM_TOPIC", "") or TOPIC_ROTATION[day_of_year % len(TOPIC_ROTATION)]


# ── STEP 1: SEARCH FOR NEWS (Serper — free tier) ──────────────────────
def search_news(topic: str) -> str:
    if not SERPER_API_KEY:
        print("No SERPER_API_KEY — writing from Gemini knowledge only")
        return f"Topic: {topic}. Write using your current knowledge of this topic."

    url = "https://google.serper.dev/news"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": topic, "num": 3}  # reduced to 3

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        articles = r.json().get("news", [])
        lines = []
        for a in articles[:3]:
            lines.append(f"- {a.get('title','')} ({a.get('source','')}, {a.get('date','')}): {a.get('snippet','')}")
        result = "\n".join(lines)
        print(f"Found {len(articles)} news articles")
        return result
    except Exception as e:
        print(f"Search failed: {e} — continuing without live news")
        return f"Topic: {topic}"


# ── STEP 2: CALL GEMINI API (free) ───────────────────────────────────
def generate_article(topic: str) -> dict:

    prompt = f"""You are the writer for EasyEquity, a stock research and financial education website.
Write a sharp, plain-English financial article published today ({TODAY}).
Tone: intelligent but accessible. Like a smart friend who works in finance.
Style: direct sentences, no fluff, clear takeaways. Connect the topic to what it means for everyday investors.

Topic: {topic}

Return ONLY raw JSON — absolutely no markdown, no backticks, no explanation before or after:
{{
  "title": "Article title (6-12 words)",
  "subtitle": "One sentence hook (20-30 words)",
  "tag": "One of: Geopolitics | Markets | Fed Watch | EM Focus | Macro | Finance 101",
  "read_time": "X min read",
  "sections": [
    {{
      "heading": "Section heading",
      "body": "2-3 paragraphs separated by <br><br>. Use <strong> for key terms. No h tags.",
      "callout": null
    }},
    {{
      "heading": "Section heading",
      "body": "...",
      "callout": {{"label": "KEY INSIGHT", "text": "One key insight in 2 sentences."}}
    }}
  ],
  "key_takeaway": "2 sentence bottom line for investors.",
  "slug": "short-url-slug"
}}

Write 4 sections. Keep it concise — 400-500 words total."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
    }

    for attempt in range(4):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=90)
            r.raise_for_status()
            break
        except requests.exceptions.HTTPError:
            if r.status_code == 429 and attempt < 3:
                wait = 20 * (attempt + 1)
                print(f"Rate limited — waiting {wait}s before retry {attempt+2}/4...")
                time.sleep(wait)
            else:
                raise

    raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw = re.sub(r"^```json\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"^```\s*", "", raw, flags=re.MULTILINE)
    raw = raw.strip().strip("`")

    return json.loads(raw)


# ── STEP 3: BUILD HTML ────────────────────────────────────────────────
def build_html(article: dict, logo_b64: str) -> str:
    sections_html = ""
    for sec in article.get("sections", []):
        sections_html += f'<h2 class="rv">{sec["heading"]}</h2>\n'
        sections_html += f'<div class="p rv">{sec["body"]}</div>\n'
        if sec.get("callout"):
            c = sec["callout"]
            sections_html += f'''<div class="ib rv">
  <div class="il">{c["label"]}</div>
  <div class="it">{c["text"]}</div>
</div>\n'''

    logo_src = f"data:image/png;base64,{logo_b64}" if logo_b64 else ""
    fav_tag  = f'<link rel="icon" type="image/png" href="{logo_src}">' if logo_src else ""
    nav_img  = f'<img src="{logo_src}" alt="EasyEquity" style="height:30px;display:block;">' if logo_src else '<span style="color:#fff;font-weight:800;font-size:17px;">Easy<b style=\'color:#3b82f6\'>Equity</b></span>'
    foot_img = f'<img src="{logo_src}" alt="EasyEquity" style="height:24px;display:block;opacity:0.7;">' if logo_src else ""

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
{fav_tag}
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{article["title"]} | Easy Equity</title>
<meta name="description" content="{article["subtitle"]}">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@300;400;500&family=Playfair+Display:ital,wght@0,700;1,500&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
:root{{--bg:#0f1117;--glass:rgba(255,255,255,0.04);--gb:rgba(255,255,255,0.09);--blue:#3b82f6;--blue-d:#1a4fd6;--ac:#3b82f6;--acl:rgba(59,130,246,0.1);--text:#f1f5f9;--mid:rgba(241,245,249,0.65);--dim:rgba(241,245,249,0.35);}}
html{{scroll-behavior:smooth;}}
body{{font-family:'Manrope',sans-serif;background:var(--bg);color:var(--text);overflow-x:hidden;line-height:1.7;}}
#cv{{position:fixed;inset:0;z-index:0;pointer-events:none;}}
.pw{{position:relative;z-index:1;}}
nav{{background:rgba(15,17,23,0.88);backdrop-filter:blur(20px);border-bottom:1px solid var(--gb);padding:0 52px;display:flex;align-items:center;justify-content:space-between;height:62px;position:sticky;top:0;z-index:100;}}
.logo{{display:flex;align-items:center;gap:9px;text-decoration:none;}}
.nb{{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--dim);text-decoration:none;display:flex;align-items:center;gap:6px;padding:7px 14px;border:1px solid var(--gb);border-radius:7px;transition:all .18s;}}
.nb:hover{{color:#fff;border-color:rgba(255,255,255,0.2);background:var(--glass);}}
.hero{{padding:64px 52px 44px;max-width:860px;margin:0 auto;}}
.ew{{display:flex;align-items:center;gap:10px;margin-bottom:20px;flex-wrap:wrap;}}
.etag{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;padding:5px 12px;border-radius:4px;font-weight:500;background:var(--acl);color:var(--ac);border:1px solid var(--ac);opacity:0.85;}}
.edate{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--dim);}}
.etime{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--dim);}}
h1{{font-family:'Playfair Display',serif;font-size:44px;font-weight:700;color:#fff;line-height:1.1;letter-spacing:-.5px;margin-bottom:16px;}}
.sub{{font-size:17px;color:var(--mid);line-height:1.65;margin-bottom:26px;font-style:italic;border-left:3px solid var(--ac);padding-left:16px;}}
.body{{max-width:720px;margin:0 auto;padding:0 52px 80px;}}
h2{{font-size:22px;font-weight:800;color:#fff;letter-spacing:-.3px;margin:44px 0 14px;padding-bottom:10px;border-bottom:1px solid var(--gb);}}
.p{{font-size:15px;color:var(--mid);line-height:1.82;margin-bottom:18px;}}
.p strong{{color:var(--text);font-weight:700;}}
.ib{{background:var(--acl);border:1px solid rgba(59,130,246,0.3);border-radius:10px;padding:20px 24px;margin:26px 0;}}
.il{{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--ac);text-transform:uppercase;margin-bottom:7px;}}
.it{{font-size:14px;color:var(--mid);line-height:1.72;}}
.it strong{{color:var(--text);}}
.verdict-box{{margin:36px 0;padding:28px 32px;background:linear-gradient(135deg,rgba(59,130,246,0.08),rgba(59,130,246,0.03));border:1px solid rgba(59,130,246,0.3);border-radius:14px;}}
.verdict-label{{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:3px;color:var(--ac);text-transform:uppercase;margin-bottom:10px;}}
.verdict-body{{font-size:14px;color:var(--mid);line-height:1.8;}}
.fnav{{max-width:720px;margin:0 auto;padding:0 52px 52px;display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;}}
.fb{{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--dim);text-decoration:none;padding:9px 15px;border:1px solid var(--gb);border-radius:7px;transition:all .18s;}}
.fb:hover{{color:#fff;border-color:rgba(255,255,255,0.2);}}
.fs{{font-size:13px;font-weight:700;color:#fff;text-decoration:none;padding:9px 18px;background:var(--blue-d);border-radius:7px;transition:all .18s;}}
.fs:hover{{background:var(--blue);}}
footer{{background:rgba(11,21,38,0.9);border-top:1px solid var(--gb);padding:26px 52px;backdrop-filter:blur(10px);}}
.fi{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;}}
.fd{{font-family:'IBM Plex Mono',monospace;font-size:9px;color:rgba(255,255,255,0.15);max-width:420px;line-height:1.6;}}
.rv{{opacity:0;transform:translateY(18px);transition:opacity .5s ease,transform .5s ease;}}
.rv.on{{opacity:1;transform:translateY(0);}}
@media(max-width:768px){{nav,footer,.fnav{{padding-left:18px;padding-right:18px;}}.hero,.body{{padding-left:18px;padding-right:18px;}}h1{{font-size:28px;}}}}
</style>
</head>
<body>
<canvas id="cv"></canvas>
<div class="pw">
<nav>
  <a href="index.html" class="logo">{nav_img}</a>
  <a href="index.html#articles" class="nb">← Back to Articles</a>
</nav>
<div class="hero">
  <div class="ew rv">
    <span class="etag">{article["tag"]}</span>
    <span class="edate">{TODAY}</span>
    <span class="etime">{article["read_time"]}</span>
  </div>
  <h1 class="rv">{article["title"]}</h1>
  <div class="sub rv">{article["subtitle"]}</div>
</div>
<div class="body">
{sections_html}
<div class="verdict-box rv">
  <div class="verdict-label">Key Takeaway</div>
  <div class="verdict-body">{article["key_takeaway"]}</div>
</div>
</div>
<div class="fnav">
  <a href="index.html#articles" class="fb">← All Articles</a>
  <a href="https://himanrbfintalk.substack.com" target="_blank" class="fs">Follow on Substack →</a>
</div>
<footer><div class="fi">{foot_img}<div class="fd">For informational purposes only. Not financial advice. Always do your own research.</div></div></footer>
</div>
<script>
(function(){{const c=document.getElementById('cv');const x=c.getContext('2d');let W,H,n=[];const N=50;function r(){{W=c.width=window.innerWidth;H=c.height=window.innerHeight;}}function i(){{n=[];for(let k=0;k<N;k++)n.push({{x:Math.random()*W,y:Math.random()*H,vx:(Math.random()-.5)*.18,vy:(Math.random()-.5)*.18,r:Math.random()*1.3+0.3}});}}function d(){{x.clearRect(0,0,W,H);for(let a=0;a<N;a++){{for(let b=a+1;b<N;b++){{const dx=n[a].x-n[b].x,dy=n[a].y-n[b].y,dist=Math.sqrt(dx*dx+dy*dy);if(dist<120){{x.beginPath();x.moveTo(n[a].x,n[a].y);x.lineTo(n[b].x,n[b].y);x.strokeStyle=`rgba(148,163,184,${{(1-dist/120)*.12}})`;x.lineWidth=.5;x.stroke();}}}}x.beginPath();x.arc(n[a].x,n[a].y,n[a].r,0,Math.PI*2);x.fillStyle='rgba(203,213,225,0.4)';x.fill();n[a].x+=n[a].vx;n[a].y+=n[a].vy;if(n[a].x<0||n[a].x>W)n[a].vx*=-1;if(n[a].y<0||n[a].y>H)n[a].vy*=-1;}}requestAnimationFrame(d);}}window.addEventListener('resize',()=>{{r();i();}});r();i();d();}})();
const o=new IntersectionObserver(e=>e.forEach(en=>{{if(en.isIntersecting)en.target.classList.add('on');}}),{{threshold:0.06}});document.querySelectorAll('.rv').forEach(el=>o.observe(el));
</script>
</body>
</html>'''


# ── STEP 4: UPDATE index.html ─────────────────────────────────────────
def update_index(article: dict, filename: str, index_path: Path):
    if not index_path.exists():
        print(f"index.html not found at {index_path}")
        return

    content = index_path.read_text(encoding="utf-8")
    new_card = f'''    <!-- AUTO: {SLUG_DATE} -->
    <a href="{filename}" class="art-card rv">
      <div class="art-meta">
        <span class="art-tag">{article["tag"]}</span>
        <span class="art-date">{TODAY}</span>
      </div>
      <div class="art-title">{article["title"]}</div>
      <div class="art-sub">{article["subtitle"]}</div>
      <div class="art-read">{article["read_time"]} →</div>
    </a>
'''
    marker = '<div class="art-grid">'
    if marker in content:
        content = content.replace(marker, marker + "\n" + new_card, 1)
        index_path.write_text(content, encoding="utf-8")
        print("index.html updated with new card")
    else:
        print("art-grid marker not found in index.html — card not added")


# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set. Add it as a GitHub Secret.")
        sys.exit(1)

    repo_root = Path(__file__).parent.parent
    logo_b64  = (repo_root / "logo.b64").read_text().strip() if (repo_root / "logo.b64").exists() else ""

    print(f"Topic today: {TOPIC}")
    print("Calling Gemini API...")
    article = generate_article(TOPIC)
    print(f"Title: {article['title']}")

    slug     = re.sub(r"[^a-z0-9\-]", "", article.get("slug", "article").lower().replace(" ", "-"))
    filename = f"Article_{SLUG_DATE}_{slug}.html"
    html     = build_html(article, logo_b64)

    out_path = repo_root / filename
    out_path.write_text(html, encoding="utf-8")
    print(f"Saved: {filename}")

    update_index(article, filename, repo_root / "index.html")
    print(f"Done! New article: {filename}")


if __name__ == "__main__":
    main()
