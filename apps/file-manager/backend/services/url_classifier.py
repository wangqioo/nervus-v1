import re
from urllib.parse import urlparse, urljoin

import httpx

from backend.utils.config import URL_PATTERNS, LINKBOX_API_URL, LINKBOX_API_KEY

# Mobile WeChat UA — makes mp.weixin.qq.com return full article HTML
_WX_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36 "
    "MicroMessenger/8.0.43.2560(0x28002B37) NetType/WIFI Language/zh_CN"
)
_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def classify_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        for link_type, patterns in URL_PATTERNS.items():
            if any(p in host for p in patterns):
                return link_type
    except Exception:
        pass
    return "generic"


def _meta(html: str, prop: str, attr: str = "property") -> str:
    for pat in [
        rf'<meta[^>]*{attr}=["\'](?:{prop})["\'][^>]*content=["\'](.*?)["\']',
        rf'<meta[^>]*content=["\'](.*?)["\'][^>]*{attr}=["\'](?:{prop})["\']',
    ]:
        m = re.search(pat, html, re.I | re.S)
        if m:
            return m.group(1).strip()
    return ""


def _bs(html: str):
    """Return a BeautifulSoup object, falling back gracefully if lxml is missing."""
    from bs4 import BeautifulSoup
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


async def fetch_linkbox(url: str) -> dict | None:
    """
    Call the LinkBox API to parse any URL.
    Returns a normalized dict on success, None if API is not configured or call fails.

    LinkBox API contract (fill in when you get the spec):
      POST  {LINKBOX_API_URL}
      Headers: Authorization: Bearer {LINKBOX_API_KEY}  (or adjust to actual auth scheme)
      Body:   {"url": "<target url>"}
      Response fields used:
        .title        → summary
        .description  → description
        .content      → fed to GLM if present (for richer AI summary)
        .cover / .image / .og_image  → og_image
        .author / .source_name       → included in description
        .keywords / .tags            → keywords
    """
    if not LINKBOX_API_URL or not LINKBOX_API_KEY:
        return None  # not configured — fall through to built-in parser

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                LINKBOX_API_URL,
                json={"url": url},
                headers={
                    "Authorization": f"Bearer {LINKBOX_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            r.raise_for_status()
            data = r.json()

        # ── Normalize response fields ──────────────────────────
        # Adjust key names below once you have the real API spec
        title       = data.get("title") or data.get("name") or ""
        description = data.get("description") or data.get("summary") or ""
        og_image    = (data.get("cover") or data.get("image")
                       or data.get("og_image") or data.get("thumbnail") or None)
        author      = data.get("author") or data.get("source_name") or ""
        raw_kw      = data.get("keywords") or data.get("tags") or []
        keywords    = raw_kw if isinstance(raw_kw, list) else [k.strip() for k in str(raw_kw).split(",") if k.strip()]
        content     = data.get("content") or data.get("text") or ""

        # If LinkBox returned full content, run it through GLM for a richer summary
        if content and len(content) > 100:
            ai = await _ai_summarize_wechat(title, author, "", content[:2000])
            return {**ai, "og_image": og_image,
                    "favicon_url": _favicon_for(url)}

        return {
            "summary":     (title or url)[:50],
            "description": (f"{author}  {description}".strip() or f"来自 {urlparse(url).netloc}")[:200],
            "keywords":    keywords or [urlparse(url).netloc.lstrip("www.")],
            "highlights":  [],
            "og_image":    og_image,
            "favicon_url": _favicon_for(url),
        }

    except Exception:
        return None  # fall through to built-in parser


async def extract_wechat_markdown(url: str) -> dict:
    """Fetch WeChat article and return full content as markdown.
    Returns {"title", "author", "pub_time", "markdown"}.
    """
    headers = {
        "User-Agent": _WX_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://mp.weixin.qq.com/",
    }
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers=headers) as client:
            r = await client.get(url)
            html = r.text
    except Exception as e:
        return {"error": f"请求失败: {e}"}

    try:
        soup = _bs(html)
    except Exception as e:
        return {"error": f"解析失败: {e}"}

    for sel in ["script", "style", "svg", ".qr_code_pc_outer", ".tips_global",
                ".weapp_text_link", "#js_pc_qr_code", ".rich_media_tool",
                ".Reward", ".FollowButton"]:
        for el in soup.select(sel):
            el.decompose()

    title = (
        _text(soup.select_one("#activity-name"))
        or _text(soup.select_one(".rich_media_title"))
        or _meta(html, "og:title")
        or "微信文章"
    )
    author = _text(soup.select_one("#js_name")) or ""
    pub_time = _text(soup.select_one("#publish_time")) or ""
    if not pub_time:
        metas = soup.select(".rich_media_meta_text")
        if metas:
            pub_time = _text(metas[-1])

    # Try to get content from #js_content, resolve data-src → src
    content_el = soup.select_one("#js_content")

    # Fallback: JsDecode
    if not content_el or not content_el.get_text(strip=True):
        for pattern in [
            r'\bcontent_noencode\s*:\s*JsDecode\([\'"]([^\'"]+)[\'"]\)',
            r'\bcontent\s*:\s*JsDecode\([\'"]([^\'"]+)[\'"]\)',
        ]:
            m = re.search(pattern, html)
            if m:
                decoded_html = _jsdecode(m.group(1))
                try:
                    content_el = _bs(f"<div>{decoded_html}</div>")
                except Exception:
                    pass
                break

    if not content_el:
        return {"error": "无法提取文章正文"}

    # Resolve lazy-loaded images
    for img in content_el.find_all("img", attrs={"data-src": True}):
        img["src"] = img["data-src"]
        img.attrs = {"src": img["data-src"]}  # strip other attrs

    # Convert to markdown via simple traversal
    md = _html_to_markdown(content_el)

    return {
        "title": title,
        "author": author,
        "pub_time": pub_time,
        "markdown": md.strip(),
    }


def _html_to_markdown(el) -> str:
    """Simple recursive HTML→Markdown converter for WeChat article content."""
    from bs4 import NavigableString, Tag

    def walk(node, depth=0) -> str:
        if isinstance(node, NavigableString):
            t = str(node)
            return t if t.strip() else (" " if t else "")

        if not isinstance(node, Tag):
            return ""

        tag = node.name.lower() if node.name else ""
        children = "".join(walk(c, depth) for c in node.children)
        children = children.strip()

        if tag in ("script", "style", "svg"):
            return ""
        if tag in ("p", "div", "section"):
            return f"\n\n{children}\n\n" if children else ""
        if tag == "br":
            return "\n"
        if tag == "h1":
            return f"\n\n# {children}\n\n"
        if tag == "h2":
            return f"\n\n## {children}\n\n"
        if tag == "h3":
            return f"\n\n### {children}\n\n"
        if tag in ("h4", "h5", "h6"):
            return f"\n\n#### {children}\n\n"
        if tag == "strong" or tag == "b":
            return f"**{children}**" if children else ""
        if tag == "em" or tag == "i":
            return f"*{children}*" if children else ""
        if tag == "blockquote":
            lines = children.splitlines()
            return "\n" + "\n".join(f"> {l}" for l in lines) + "\n"
        if tag == "ul":
            items = [f"- {walk(li).strip()}" for li in node.find_all("li", recursive=False)]
            return "\n" + "\n".join(items) + "\n"
        if tag == "ol":
            items = [f"{i+1}. {walk(li).strip()}" for i, li in enumerate(node.find_all("li", recursive=False))]
            return "\n" + "\n".join(items) + "\n"
        if tag == "li":
            return children
        if tag == "a":
            href = node.get("href", "")
            if href and children:
                return f"[{children}]({href})"
            return children
        if tag == "img":
            src = node.get("src") or node.get("data-src") or ""
            alt = node.get("alt") or node.get("data-alt") or ""
            if src:
                # Route through image proxy
                proxied = f"/api/image-proxy?url={src}"
                return f"\n\n![{alt}]({proxied})\n\n"
            return ""
        if tag == "code":
            return f"`{children}`"
        if tag == "pre":
            return f"\n\n```\n{children}\n```\n\n"
        if tag == "hr":
            return "\n\n---\n\n"
        if tag == "span":
            return children
        return children

    result = walk(el)
    # Collapse excessive blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _favicon_for(url: str) -> str:
    parsed = urlparse(url)
    if "weixin.qq.com" in parsed.netloc:
        return "https://res.wx.qq.com/a/wx_fed/assets/res/NTI4MWU5.ico"
    return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"


def _jsdecode(encoded: str) -> str:
    """Decode WeChat's JsDecode-encoded content (hex escapes + HTML entities)."""
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), encoded)
    s = (s.replace("&lt;", "<").replace("&gt;", ">")
          .replace("&quot;", '"').replace("&#39;", "'")
          .replace("&amp;", "&").replace("&nbsp;", " "))
    return s


def _extract_wechat_content(html: str, soup) -> str:
    """Extract article body text from WeChat HTML.

    Tries #js_content first; falls back to JsDecode-encoded payload in <script>.
    Also resolves data-src lazy images so they're counted in the text.
    """
    content_el = soup.select_one("#js_content")
    if content_el:
        # Resolve lazy-loaded images: replace data-src with src
        for img in content_el.find_all("img", attrs={"data-src": True}):
            img["src"] = img["data-src"]
        text = content_el.get_text("\n", strip=True)
        if text.strip():
            return text.strip()

    # Fallback: decode JsDecode payload from inline script
    for pattern in [
        r'\bcontent_noencode\s*:\s*JsDecode\([\'"]([^\'"]+)[\'"]\)',
        r'\bcontent\s*:\s*JsDecode\([\'"]([^\'"]+)[\'"]\)',
    ]:
        m = re.search(pattern, html)
        if m:
            decoded_html = _jsdecode(m.group(1))
            try:
                inner = _bs(decoded_html)
                text = inner.get_text("\n", strip=True)
                if text.strip():
                    return text.strip()
            except Exception:
                pass

    return _meta(html, "og:description")


def _extract_wechat_cover(html: str, soup) -> str | None:
    """Extract cover image URL from WeChat article.

    Priority: og:image → first data-src img in #js_content.
    Returns the raw WeChat CDN URL (qpic.cn / mmbiz).
    """
    og = _meta(html, "og:image")
    if og:
        return og

    content_el = soup.select_one("#js_content")
    if content_el:
        img = content_el.find("img", attrs={"data-src": True})
        if img:
            return img["data-src"]
    return None


async def fetch_wechat_summary(url: str) -> dict:
    """Fetch a WeChat public account article and return AI-generated summary fields.
    Priority: LinkBox API → direct scrape → fallback.
    """
    # 1. Try LinkBox API first (when configured)
    linkbox_result = await fetch_linkbox(url)
    if linkbox_result is not None:
        return linkbox_result

    # 2. Direct scrape with WeChat mobile UA
    headers = {
        "User-Agent": _WX_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://mp.weixin.qq.com/",
    }

    html = ""
    try:
        async with httpx.AsyncClient(
            timeout=25, follow_redirects=True, headers=headers
        ) as client:
            r = await client.get(url)
            if "text/html" not in r.headers.get("content-type", ""):
                return _wechat_fallback(url, "非 HTML 页面")
            html = r.text
    except Exception as e:
        return _wechat_fallback(url, f"网络请求失败: {e}")

    if not html:
        return _wechat_fallback(url, "页面内容为空")

    try:
        soup = _bs(html)
    except Exception as e:
        return _wechat_fallback(url, f"HTML 解析失败: {e}")

    # Remove noise elements
    for sel in ["script", "style", "svg",
                ".qr_code_pc_outer", ".tips_global", ".weapp_text_link",
                "#js_pc_qr_code", ".rich_media_tool", ".Reward", ".FollowButton"]:
        for el in soup.select(sel):
            el.decompose()

    title = (
        _text(soup.select_one("#activity-name"))
        or _text(soup.select_one(".rich_media_title"))
        or _meta(html, "og:title")
        or _meta(html, "twitter:title", "name")
        or "微信公众号文章"
    )

    author = (
        _text(soup.select_one("#js_name"))
        or _text(soup.select_one(".rich_media_meta_text"))
        or ""
    )

    # #publish_time 有时是最后一个 .rich_media_meta_text
    pub_time = _text(soup.select_one("#publish_time")) or ""
    if not pub_time:
        metas = soup.select(".rich_media_meta_text")
        if metas:
            pub_time = _text(metas[-1])

    og_image = _extract_wechat_cover(html, soup)
    content_text = _extract_wechat_content(html, soup)[:3000].strip()

    favicon_url = "https://res.wx.qq.com/a/wx_fed/assets/res/NTI4MWU5.ico"

    if content_text:
        ai_result = await _ai_summarize_wechat(title, author, pub_time, content_text)
    else:
        ai_result = {
            "summary": title[:50],
            "description": f"公众号：{author}  {pub_time}".strip() or f"来源：{url}",
            "keywords": ["公众号", "微信"],
            "highlights": [],
        }

    return {
        **ai_result,
        "og_image": og_image,
        "favicon_url": favicon_url,
    }


def _text(el) -> str:
    """Safe .get_text() from a BeautifulSoup element."""
    if el is None:
        return ""
    return el.get_text(strip=True)


def _wechat_fallback(url: str, reason: str = "") -> dict:
    return {
        "summary": "微信公众号文章",
        "description": reason or f"来源：{url}",
        "keywords": ["公众号", "微信"],
        "highlights": [],
        "og_image": None,
        "favicon_url": "https://res.wx.qq.com/a/wx_fed/assets/res/NTI4MWU5.ico",
    }


def _parse_arbor_response(resp_data: dict) -> str:
    """Extract actual answer from Arbor /models/chat response.

    Arbor returns {"model": ..., "content": ..., "reasoning_content": ...}
    When content is empty but reasoning_content has thinking, extract the answer.
    """
    content = resp_data.get("content", "").strip()
    if content:
        return content

    reasoning = resp_data.get("reasoning_content", "").strip()
    if not reasoning:
        return ""

    if "<|reserved_200|>" in reasoning:
        return reasoning.split("<|reserved_200|>")[-1].strip()

    if "</think>" in reasoning:
        return reasoning.split("</think>")[-1].strip()

    return reasoning.strip()


async def _ai_summarize_wechat(title: str, author: str, pub_time: str, content: str) -> dict:
    """Send extracted article text to platform LLM for structured summarization."""
    import json
    import os

    arbor_url = os.getenv("ARBOR_URL", "http://nervus-arbor:8090")
    prompt = (
        f"文章标题：{title}\n"
        f"公众号：{author}\n"
        f"发布时间：{pub_time}\n"
        f"正文节选：\n{content}\n\n"
        "请生成JSON格式简介（只输出JSON）：\n"
        "{\n"
        '  "summary": "一句话概括文章核心（20字内）",\n'
        '  "description": "文章主要内容摘要（100字内）",\n'
        '  "keywords": ["关键词1", "关键词2", "关键词3"],\n'
        '  "highlights": ["亮点1", "亮点2"]\n'
        "}"
    )
    messages = [
        {"role": "system", "content": "你是一个公众号文章摘要助手，擅长提炼文章核心观点。"},
        {"role": "user", "content": f"/no_think {prompt}"},
    ]
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{arbor_url}/models/chat",
                json={
                    "model": "",
                    "messages": messages,
                    "max_tokens": 512,
                },
            )
            resp.raise_for_status()
            raw = _parse_arbor_response(resp.json())
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            return json.loads(m.group())
    except Exception:
        pass

    return {
        "summary": title[:50],
        "description": f"公众号：{author}  {content[:120]}".strip(),
        "keywords": ["公众号", "微信"],
        "highlights": [],
    }


async def fetch_bilibili_summary(url: str) -> dict:
    bvid_m = re.search(r"BV[\w]+", url)
    if bvid_m:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://api.bilibili.com/x/web-interface/view?bvid={bvid_m.group()}"
                )
                d = r.json().get("data", {})
            title = d.get("title", "B站视频")
            desc = (d.get("desc") or "")[:200]
            pic = d.get("pic") or None
            owner = d.get("owner", {}).get("name", "")
            return {
                "summary": title[:50],
                "description": f"UP主：{owner}  {desc}".strip(),
                "keywords": ["B站", "视频", owner],
                "highlights": [],
                "og_image": pic,
                "favicon_url": "https://www.bilibili.com/favicon.ico",
            }
        except Exception:
            pass
    return await fetch_generic_summary(url)


async def fetch_generic_summary(url: str) -> dict:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    title = description = og_image = favicon_url = None

    try:
        async with httpx.AsyncClient(
            timeout=12, follow_redirects=True,
            headers={"User-Agent": _DESKTOP_UA}
        ) as client:
            r = await client.get(url)
            html = r.text

        _title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = (
            _meta(html, "og:title")
            or _meta(html, "twitter:title", "name")
            or _meta(html, "title", "name")
            or (_title_m.group(1) if _title_m else None)
            or parsed.netloc
        )
        title = re.sub(r"<[^>]+>", "", title).strip()

        description = (
            _meta(html, "og:description")
            or _meta(html, "description", "name")
            or ""
        )

        og_raw = _meta(html, "og:image") or _meta(html, "twitter:image", "name")
        if og_raw:
            og_image = og_raw if og_raw.startswith("http") else urljoin(base, og_raw)

        fav_raw = ""
        for pat in [
            r'<link[^>]*rel=["\'](?:shortcut icon|icon)["\'][^>]*href=["\'](.*?)["\']',
            r'<link[^>]*href=["\'](.*?)["\'][^>]*rel=["\'](?:shortcut icon|icon)["\']',
        ]:
            m = re.search(pat, html, re.I)
            if m:
                fav_raw = m.group(1)
                break
        favicon_url = (
            (fav_raw if fav_raw.startswith("http") else urljoin(base, fav_raw))
            if fav_raw
            else f"{base}/favicon.ico"
        )

    except Exception:
        pass

    return {
        "summary": (title or parsed.netloc)[:50],
        "description": (description or f"来自 {parsed.netloc}")[:200],
        "keywords": [parsed.netloc.lstrip("www.")],
        "highlights": [],
        "og_image": og_image,
        "favicon_url": favicon_url,
    }
