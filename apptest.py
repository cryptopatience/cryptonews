"""
app.py — Streamlit 크립토 뉴스 대시보드
"""

import re
import datetime
import os
import requests
from bs4 import BeautifulSoup
import streamlit as st

st.set_page_config(
    page_title="크립토 뉴스 리포트",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dotenv import load_dotenv
load_dotenv()

def get_secret(key: str) -> str:
    try:
        return st.secrets.get(key, "") or os.getenv(key, "")
    except Exception:
        return os.getenv(key, "")

CRYPTOPANIC_API_KEY = get_secret("CRYPTOPANIC_API_KEY")
OPENAI_API_KEY      = get_secret("OPENAI_API_KEY")
GEMINI_API_KEY      = get_secret("GEMINI_API_KEY")
APP_PASSWORD        = get_secret("APP_PASSWORD")


# ── 비밀번호 보호 ────────────────────────────────

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if APP_PASSWORD and not st.session_state.authenticated:
    st.markdown("""
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .lock-wrap {
        max-width: 380px; margin: 10vh auto 0;
        background: #161b22; border: 1px solid #30363d;
        border-radius: 20px; padding: 48px 40px;
        text-align: center; box-shadow: 0 24px 64px rgba(0,0,0,.6);
    }
    .lock-wrap h2 {
        font-size: 1.4rem; font-weight: 700; color: #f0f6fc; margin-bottom: 6px;
    }
    .lock-wrap p { color: #8b949e; font-size: .88rem; margin-bottom: 28px; }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="lock-wrap"><div style="font-size:2.6rem">🔐</div><h2>크립토 뉴스 리포트</h2><p>접근하려면 비밀번호를 입력하세요</p></div>', unsafe_allow_html=True)
    pw = st.text_input("비밀번호", type="password", placeholder="••••", label_visibility="collapsed")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("잠금 해제", type="primary", use_container_width=True):
            if pw == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    st.stop()

NOW_UTC       = datetime.datetime.utcnow()
NOW_KST       = NOW_UTC + datetime.timedelta(hours=9)
TODAY_STR     = NOW_KST.strftime("%Y-%m-%d")
YESTERDAY_STR = (NOW_KST - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

SOURCE_COLORS = {
    "cryptopanic":    "#f7931a",
    "coindesk":       "#1a73e8",
    "cryptonews.net": "#2ea043",
    "coincarp":       "#8b5cf6",
    "crypto.news":    "#06b6d4",
    "cryptonews.com": "#ef4444",
    "the block":      "#f59e0b",
    "decrypt":        "#00d4aa",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── CSS ────────────────────────────────────────
st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
    border: 1px solid #21262d; border-radius: 16px;
    padding: 32px 28px 24px; text-align: center; margin-bottom: 24px;
}
.main-header h1 {
    font-size: 2rem; font-weight: 800;
    background: linear-gradient(90deg, #f7931a, #627eea, #00d4aa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 8px;
}
.main-header .sub { color: #8b949e; font-size: .9rem; }
.news-card {
    background: #161b22; border: 1px solid #21262d;
    border-radius: 10px; padding: 14px 16px; margin-bottom: 8px;
}
.news-card:hover { border-color: #388bfd; }
.news-title { font-size: .93rem; font-weight: 500; color: #e6edf3; line-height: 1.5; margin-bottom: 5px; }
.news-title a { color: #e6edf3; text-decoration: none; }
.news-title a:hover { color: #58a6ff; }
.news-desc { font-size: .8rem; color: #8b949e; line-height: 1.5; margin-bottom: 7px; }
.news-meta { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.src-badge { font-size: .7rem; border: 1px solid; border-radius: 4px; padding: 1px 7px; font-weight: 600; }
.time-tag { font-size: .72rem; color: #6e7681; }
.sec-title {
    font-size: 1rem; font-weight: 700; color: #f0f6fc;
    margin: 24px 0 12px; padding-left: 10px; border-left: 4px solid #f7931a;
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="main-header">
  <h1>📰 크립토 뉴스 종합 리포트</h1>
  <div class="sub">멀티소스 통합 수집 · AI 요약 &nbsp;|&nbsp; {TODAY_STR} (KST)</div>
</div>
""", unsafe_allow_html=True)


# ── 사이드바 ────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    use_ai = st.toggle("AI 요약 생성", value=bool(GEMINI_API_KEY or OPENAI_API_KEY))
    if use_ai:
        _ai_options = []
        if GEMINI_API_KEY:   _ai_options.append("Gemini 2.5 Pro")
        if OPENAI_API_KEY:   _ai_options.append("GPT-4o-mini")
        if not _ai_options:  _ai_options = ["(API 키 없음)"]
        ai_provider = st.selectbox("AI 제공자", _ai_options)
    else:
        ai_provider = ""
    st.markdown("---")
    st.markdown("**수집 소스**")
    src_cryptopanic  = st.checkbox("CryptoPanic API", value=bool(CRYPTOPANIC_API_KEY))
    src_coindesk     = st.checkbox("CoinDesk", value=True)
    src_cryptonews_n = st.checkbox("cryptonews.net", value=True)
    src_coincarp     = st.checkbox("coincarp.com", value=True)
    src_theblock     = st.checkbox("The Block (RSS)", value=True)
    src_cryptonews_c = st.checkbox("cryptonews.com", value=True)
    src_decrypt      = st.checkbox("Decrypt (RSS)", value=True)
    st.markdown("---")
    run_btn = st.button("🚀 뉴스 수집 시작", type="primary", use_container_width=True)
    st.markdown("---")
    st.caption(f"KST {NOW_KST.strftime('%Y-%m-%d %H:%M')}")


# ── 유틸 ───────────────────────────────────────

def src_color(source: str) -> str:
    low = source.lower()
    for k, v in SOURCE_COLORS.items():
        if k in low:
            return v
    return "#8b949e"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = BeautifulSoup(text, "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", cleaned).strip()


def make_item(title, url="", source="", published_at="", description=""):
    return {
        "title": re.sub(r"\s+", " ", title).strip(),
        "url": url, "source": source,
        "published_at": published_at,
        "description": _strip_html(description or ""),
    }


def is_recent(pub: str) -> bool:
    if not pub:
        return True
    return pub[:10] >= YESTERDAY_STR


def dedup(news_list: list) -> list:
    seen, result = {}, []
    for item in news_list:
        key = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:60]
        if key not in seen:
            seen[key] = True
            result.append(item)
    return result


def find_time_in_parents(element) -> str:
    el = element
    for _ in range(6):
        el = el.parent
        if not el:
            break
        t = el.find("time")
        if t:
            return t.get("datetime", "")
    return ""


def utc_to_kst(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (dt + datetime.timedelta(hours=9)).strftime("%m/%d %H:%M")
    except Exception:
        return iso_str[:16]


# ── 스크래퍼 ────────────────────────────────────

def fetch_cryptopanic(api_key: str) -> list:
    if not api_key:
        return []
    try:
        r = requests.get(
            "https://cryptopanic.com/api/developer/v2/posts/",
            params={"auth_token": api_key, "public": "true", "kind": "news", "regions": "en"},
            headers=HEADERS, timeout=15,
        )
        if r.status_code in (403, 429):
            return []
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    results = []
    for item in data.get("results", []):
        pub = item.get("published_at", "")
        if not is_recent(pub):
            continue
        results.append(make_item(
            title=item.get("title", ""), source="CryptoPanic",
            published_at=pub, description=item.get("description", "") or "",
        ))
    return results


def fetch_coindesk() -> list:
    try:
        r = requests.get("https://www.coindesk.com/latest-crypto-news", headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return []
    results, seen = [], set()
    for sel in ["a[href*='/markets/']", "a[href*='/business/']", "a[href*='/tech/']", "a[href*='/policy/']"]:
        for lk in soup.select(sel):
            href  = lk.get("href", "")
            title = lk.get_text(strip=True)
            if not title or len(title) < 15 or href in seen:
                continue
            seen.add(href)
            full_url = f"https://www.coindesk.com{href}" if href.startswith("/") else href
            pub = find_time_in_parents(lk)
            if pub and not is_recent(pub):
                continue
            results.append(make_item(title=title, url=full_url, source="CoinDesk", published_at=pub))
    return results


def fetch_cryptonews_net() -> list:
    results, seen = [], set()
    for url in ["https://cryptonews.net/news/bitcoin/", "https://cryptonews.net/news/ethereum/", "https://cryptonews.net/"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception:
            continue
        for item in soup.select(".news-item"):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            full_url = f"https://cryptonews.net{href}" if href.startswith("/") else href
            if full_url in seen:
                continue
            seen.add(full_url)
            title_el = item.select_one(".news-item__title, h2, h3, h4, .title")
            title = title_el.get_text(strip=True) if title_el else item.get_text(separator=" ", strip=True)[:120]
            time_el = item.find("time")
            pub = time_el.get("datetime", "") if time_el else ""
            if pub and not is_recent(pub):
                continue
            src_el = item.select_one(".news-item__source, .source")
            source = src_el.get_text(strip=True) if src_el else "cryptonews.net"
            results.append(make_item(title=title, url=full_url, source=source or "cryptonews.net", published_at=pub))
    return results


def fetch_coincarp() -> list:
    results, seen = [], set()
    for url in ["https://www.coincarp.com/news/bitcoin/", "https://www.coincarp.com/news/ethereum/", "https://www.coincarp.com/news/"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception:
            continue
        for lk in soup.find_all("a", href=True):
            href = lk.get("href", "")
            if not href.startswith("http") or "coincarp.com" in href:
                continue
            raw   = lk.get_text(strip=True)
            title = re.sub(r"^\d+\s*(min|mins|hour|hours|sec|secs|day|days)\s*(Ago|ago)\s*", "", raw).strip()
            if not title or len(title) < 15 or href in seen:
                continue
            seen.add(href)
            m = re.search(r"(\d+)\s*(min|mins|hour|hours)", raw)
            pub = ""
            if m:
                val  = int(m.group(1))
                delta = datetime.timedelta(minutes=val) if "min" in m.group(2) else datetime.timedelta(hours=val)
                pub = (NOW_UTC - delta).strftime("%Y-%m-%dT%H:%M:%SZ")
            dm = re.search(r"https?://(?:www\.)?([^/]+)", href)
            source = dm.group(1) if dm else "coincarp"
            results.append(make_item(title=title, url=href, source=source, published_at=pub))
    return results


def fetch_theblock_rss() -> list:
    results = []
    for rss_url in ["https://www.theblock.co/rss.xml", "https://www.theblock.co/feeds/rss.xml"]:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "xml")
            for item in (soup.find_all("item") or soup.find_all("entry")):
                title_el = item.find("title")
                link_el  = item.find("link")
                pub_el   = item.find("pubDate") or item.find("published") or item.find("updated")
                desc_el  = item.find("description") or item.find("summary")
                title   = title_el.get_text(strip=True) if title_el else ""
                link    = link_el.get_text(strip=True)  if link_el  else ""
                pub_raw = pub_el.get_text(strip=True)   if pub_el   else ""
                desc    = BeautifulSoup(desc_el.get_text(strip=True), "html.parser").get_text(strip=True)[:200] if desc_el else ""
                if not title:
                    continue
                try:
                    from email.utils import parsedate_to_datetime
                    pub_iso = parsedate_to_datetime(pub_raw).strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    pub_iso = pub_raw[:19]
                if pub_iso and not is_recent(pub_iso):
                    continue
                results.append(make_item(title=title, url=link, source="The Block", published_at=pub_iso, description=desc))
            if results:
                break
        except Exception:
            continue
    return results


def fetch_cryptonews_com() -> list:
    results, seen = [], set()
    for url in ["https://cryptonews.com/news/", "https://cryptonews.com/news/bitcoin-news/", "https://cryptonews.com/news/ethereum-news/"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception:
            continue
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            full_url = f"https://cryptonews.com{href}" if href.startswith("/") else href
            if not re.search(r"cryptonews\.com/news/[a-z]", full_url):
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 15 or full_url in seen:
                continue
            seen.add(full_url)
            pub = find_time_in_parents(a)
            if pub and not is_recent(pub):
                continue
            results.append(make_item(title=title, url=full_url, source="cryptonews.com", published_at=pub))
    return results


def fetch_decrypt() -> list:
    results = []
    try:
        r = requests.get("https://decrypt.co/feed", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "xml")
        for item in (soup.find_all("item") or []):
            title_el = item.find("title")
            link_el  = item.find("link")
            pub_el   = item.find("pubDate")
            desc_el  = item.find("description")
            title   = title_el.get_text(strip=True) if title_el else ""
            link    = link_el.get_text(strip=True)  if link_el  else ""
            pub_raw = pub_el.get_text(strip=True)   if pub_el   else ""
            desc    = BeautifulSoup(desc_el.get_text(strip=True), "html.parser").get_text(strip=True)[:200] if desc_el else ""
            if not title:
                continue
            try:
                from email.utils import parsedate_to_datetime
                pub_iso = parsedate_to_datetime(pub_raw).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pub_iso = pub_raw[:19]
            if pub_iso and not is_recent(pub_iso):
                continue
            results.append(make_item(title=title, url=link, source="Decrypt", published_at=pub_iso, description=desc))
    except Exception:
        pass
    return results


# ── AI 요약 ─────────────────────────────────────

def build_news_text(news_list: list, limit: int = 60) -> str:
    lines = []
    for item in news_list[:limit]:
        line = f"- [{item['source']}] {item['title']}"
        if item.get("description"):
            line += f"\n  {item['description'][:120]}"
        lines.append(line)
    return "\n".join(lines)


PROMPT_QUICK = """다음은 {date} (KST) 크립토 뉴스입니다.\n\n{content}\n\n위 뉴스만을 바탕으로 한국어 Quick Summary를 작성해주세요.\n\n1. **오늘의 핵심 테마** (3~5가지, 각 1~2문장)\n2. **코인/프로젝트별 주요 이슈** (언급된 코인 중심, 각 1문장)\n3. **한줄 시장 요약** (전체를 한 문장으로)\n\n간결하게 작성해주세요."""

PROMPT_DEEP = """다음은 {date} (KST) 크립토 뉴스입니다.\n\n{content}\n\n위 뉴스만을 바탕으로 한국어 Deep Dive 심층 분석을 작성해주세요.\n\n1. **거시 경제 및 규제 환경 분석**\n2. **주요 코인별 온체인/펀더멘털 분석** (각 코인 2~4문장)\n3. **기관 투자자 동향** (ETF, 기업 보유, 기관 움직임)\n4. **리스크 요인 및 주의 포인트**\n5. **단기 시장 전망 및 투자 시사점**\n\n각 섹션을 충분히 상세하게 작성해주세요."""


def summarize_gemini(news_list: list, api_key: str):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("google-genai 패키지가 없습니다.")
        return "", ""

    client  = genai.Client(api_key=api_key)
    content = build_news_text(news_list, 60)

    def _extract(resp) -> str:
        if resp.text is not None:
            return resp.text
        try:
            return resp.candidates[0].content.parts[0].text or ""
        except Exception:
            return ""

    quick, deep = "", ""
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=PROMPT_QUICK.format(date=TODAY_STR, content=content),
            config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=8000),
        )
        quick = _extract(resp)
    except Exception as e:
        st.warning(f"Gemini Quick Summary 오류: {e}")
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=PROMPT_DEEP.format(date=TODAY_STR, content=content),
            config=types.GenerateContentConfig(temperature=0.35, max_output_tokens=16000),
        )
        deep = _extract(resp)
    except Exception as e:
        st.warning(f"Gemini Deep Dive 오류: {e}")
    return quick, deep


def summarize_openai(news_list: list, api_key: str):
    try:
        from openai import OpenAI
    except ImportError:
        st.error("openai 패키지가 없습니다.")
        return "", ""

    client  = OpenAI(api_key=api_key)
    content = build_news_text(news_list, 60)
    quick, deep = "", ""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT_QUICK.format(date=TODAY_STR, content=content)}],
            max_tokens=1200, temperature=0.4,
        )
        quick = resp.choices[0].message.content
    except Exception as e:
        st.warning(f"GPT Quick Summary 오류: {e}")
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": PROMPT_DEEP.format(date=TODAY_STR, content=content)}],
            max_tokens=2500, temperature=0.35,
        )
        deep = resp.choices[0].message.content
    except Exception as e:
        st.warning(f"GPT Deep Dive 오류: {e}")
    return quick, deep


# ── 뉴스 카드 렌더링 ────────────────────────────

def render_news_card(item: dict, idx: int):
    import html as _html
    title  = _html.escape(item.get("title", "") or "")
    url    = item.get("url", "")
    source = item.get("source", "")
    pub    = item.get("published_at", "")
    desc   = _html.escape((item.get("description", "") or "").strip())
    color  = src_color(source)
    kst    = utc_to_kst(pub)

    title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
    desc_html  = f'<div class="news-desc">{desc[:150]}</div>' if desc and desc != title else ""
    time_html  = f'<span class="time-tag">🕐 KST {kst}</span>' if kst else ""

    st.markdown(f"""
    <div class="news-card">
      <div style="display:flex;gap:10px;align-items:flex-start">
        <div style="flex-shrink:0;width:24px;height:24px;background:#21262d;border-radius:5px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:.7rem;color:#8b949e;font-weight:600;margin-top:2px">{idx}</div>
        <div style="flex:1;min-width:0">
          <div class="news-title">{title_html}</div>
          {desc_html}
          <div class="news-meta">
            <span class="src-badge" style="background:{color}22;color:{color};border-color:{color}55">{source}</span>
            {time_html}
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ── 세션 상태 초기화 ────────────────────────────

if "news_data" not in st.session_state:
    st.session_state.news_data     = []
    st.session_state.source_stats  = {}
    st.session_state.summary_quick = ""
    st.session_state.summary_deep  = ""
    st.session_state.provider      = ""


# ── 수집 실행 ───────────────────────────────────

if run_btn:
    all_news = []
    source_map: dict = {}

    tasks = []
    if src_cryptopanic and CRYPTOPANIC_API_KEY:
        tasks.append(("CryptoPanic", fetch_cryptopanic, [CRYPTOPANIC_API_KEY]))
    if src_coindesk:
        tasks.append(("CoinDesk", fetch_coindesk, []))
    if src_cryptonews_n:
        tasks.append(("cryptonews.net", fetch_cryptonews_net, []))
    if src_coincarp:
        tasks.append(("coincarp.com", fetch_coincarp, []))
    if src_theblock:
        tasks.append(("The Block", fetch_theblock_rss, []))
    if src_cryptonews_c:
        tasks.append(("cryptonews.com", fetch_cryptonews_com, []))
    if src_decrypt:
        tasks.append(("Decrypt", fetch_decrypt, []))

    with st.status("뉴스 수집 중...", expanded=True) as status:
        for name, fn, args in tasks:
            st.write(f"📡 {name} 수집 중...")
            try:
                items = fn(*args)
                all_news += items
                source_map[name] = len(items)
                st.write(f"  ✅ {name}: {len(items)}건")
            except Exception as e:
                source_map[name] = 0
                st.write(f"  ⚠️ {name}: {e}")

        all_news = dedup(all_news)
        all_news.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        st.session_state.news_data    = all_news
        st.session_state.source_stats = source_map

        # AI 요약
        st.session_state.summary_quick = ""
        st.session_state.summary_deep  = ""
        st.session_state.provider      = ""

        if use_ai and all_news:
            if ai_provider == "Gemini 2.5 Pro" and GEMINI_API_KEY:
                st.write("🤖 Gemini 2.5 Pro로 AI 요약 생성 중...")
                q, d = summarize_gemini(all_news, GEMINI_API_KEY)
                st.session_state.summary_quick = q
                st.session_state.summary_deep  = d
                st.session_state.provider      = "Gemini 2.5 Pro"
            elif ai_provider == "GPT-4o-mini" and OPENAI_API_KEY:
                st.write("🤖 GPT-4o-mini로 AI 요약 생성 중...")
                q, d = summarize_openai(all_news, OPENAI_API_KEY)
                st.session_state.summary_quick = q
                st.session_state.summary_deep  = d
                st.session_state.provider      = "GPT-4o-mini"
            else:
                st.write("⚠️ AI API 키가 없어 요약을 건너뜁니다.")

        status.update(label=f"✅ 수집 완료 — 총 {len(all_news)}건 (중복 제거 후)", state="complete")


# ── 결과 표시 ───────────────────────────────────

news_data     = st.session_state.news_data
source_stats  = st.session_state.source_stats
summary_quick = st.session_state.summary_quick
summary_deep  = st.session_state.summary_deep
provider      = st.session_state.provider

if not news_data:
    st.info("👈 사이드바에서 **뉴스 수집 시작** 버튼을 눌러주세요.")
    st.stop()

# 통계 카드
st.markdown('<div class="sec-title">📊 소스별 수집 현황</div>', unsafe_allow_html=True)
total_col, *src_cols = st.columns([1] + [1] * min(len(source_stats), 6))
with total_col:
    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid #f7931a;
                border-radius:10px;padding:14px 10px;text-align:center">
      <div style="font-size:1.5rem;font-weight:700;color:#f7931a">{len(news_data)}</div>
      <div style="font-size:.75rem;color:#8b949e;margin-top:4px">총 뉴스</div>
    </div>""", unsafe_allow_html=True)

for col, (src, cnt) in zip(src_cols, list(source_stats.items())[:6]):
    color = src_color(src)
    with col:
        st.markdown(f"""
        <div style="background:#161b22;border:1px solid #21262d;border-top:3px solid {color};
                    border-radius:10px;padding:14px 10px;text-align:center">
          <div style="font-size:1.5rem;font-weight:700;color:{color}">{cnt}</div>
          <div style="font-size:.72rem;color:#8b949e;margin-top:4px;word-break:break-all">{src}</div>
        </div>""", unsafe_allow_html=True)

# AI 요약
if summary_quick or summary_deep:
    provider_label = f" <span style='font-size:.8rem;color:#8b949e'>by {provider}</span>" if provider else ""
    st.markdown(f'<div class="sec-title">🤖 AI 분석{provider_label}</div>', unsafe_allow_html=True)
    tab_quick, tab_deep = st.tabs(["⚡ Quick Summary", "🔬 Deep Dive"])
    with tab_quick:
        st.markdown(summary_quick or "_요약 없음_")
    with tab_deep:
        st.markdown(summary_deep or "_분석 없음_")

# 뉴스 목록
st.markdown(f'<div class="sec-title">📋 전체 뉴스 목록 ({len(news_data)}건)</div>', unsafe_allow_html=True)

# 필터
col_search, col_src = st.columns([3, 1])
with col_search:
    search_q = st.text_input("🔍 검색", placeholder="키워드 입력...", label_visibility="collapsed")
with col_src:
    all_sources = sorted(set(item["source"] for item in news_data))
    filter_src  = st.selectbox("소스 필터", ["전체"] + all_sources, label_visibility="collapsed")

filtered = news_data
if search_q:
    q = search_q.lower()
    filtered = [n for n in filtered if q in n["title"].lower() or q in (n.get("description") or "").lower()]
if filter_src != "전체":
    filtered = [n for n in filtered if n["source"] == filter_src]

st.caption(f"{len(filtered)}건 표시 중")

for i, item in enumerate(filtered, 1):
    render_news_card(item, i)

st.markdown(f"""
<div style="text-align:center;padding:24px 16px;color:#6e7681;font-size:.8rem;
            border-top:1px solid #21262d;margin-top:32px">
  데이터 출처: CryptoPanic · CoinDesk · cryptonews.net · coincarp.com · The Block · cryptonews.com · Decrypt
  &nbsp;|&nbsp; 생성: {NOW_KST.strftime('%Y-%m-%d %H:%M')} KST
</div>
""", unsafe_allow_html=True)
