"""
新闻抓取模块
权威来源：路透社、BBC、纽约时报、卫报、MIT技术评论、Ars Technica
加密货币：优先 PA News 中文站 (panewslab.com)，再用 CoinDesk / The Block
"""

import re
import logging
import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    )
}

# ─── RSS 新闻源配置 ────────────────────────────────────────────────────────────
# lang: 'zh' = 中文来源, 'en' = 英文来源
RSS_SOURCES = {

    'world': [
        {'name': '法国24',     'name_en': 'France 24',       'lang': 'en', 'url': 'https://www.france24.com/en/rss'},
        {'name': '德国之声',   'name_en': 'Deutsche Welle',  'lang': 'en', 'url': 'https://rss.dw.com/rdf/rss-en-world'},
        {'name': 'NPR新闻',    'name_en': 'NPR News',        'lang': 'en', 'url': 'https://feeds.npr.org/1004/rss.xml'},
        {'name': '卫报',       'name_en': 'The Guardian',    'lang': 'en', 'url': 'https://www.theguardian.com/world/rss'},
        {'name': '半岛电视台', 'name_en': 'Al Jazeera',      'lang': 'en', 'url': 'https://www.aljazeera.com/xml/rss/all.xml'},
        {'name': 'ABC新闻',    'name_en': 'ABC News',        'lang': 'en', 'url': 'https://feeds.abcnews.com/abcnews/internationalheadlines'},
    ],

    'ai': [
        {'name': 'MIT技术评论','name_en': 'MIT Tech Review', 'lang': 'en', 'url': 'https://www.technologyreview.com/feed/'},
        {'name': 'TechCrunch', 'name_en': 'TechCrunch',     'lang': 'en', 'url': 'https://techcrunch.com/feed/'},
        {'name': 'Engadget',   'name_en': 'Engadget',        'lang': 'en', 'url': 'https://www.engadget.com/rss.xml'},
        {'name': 'Ars Technica','name_en':'Ars Technica',    'lang': 'en', 'url': 'https://feeds.arstechnica.com/arstechnica/technology-lab'},
        {'name': 'The Verge',  'name_en': 'The Verge',       'lang': 'en', 'url': 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml'},
        {'name': 'VentureBeat','name_en': 'VentureBeat',     'lang': 'en', 'url': 'https://venturebeat.com/category/ai/feed/'},
    ],

    # 加密货币：PA News 优先（中文），其次英文权威媒体
    'crypto': [
        {'name': 'PA News',      'name_en': 'PA News',       'lang': 'zh', 'url': 'https://www.panewslab.com/rss.xml'},
        {'name': 'CoinDesk',     'name_en': 'CoinDesk',      'lang': 'en', 'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/'},
        {'name': 'The Block',    'name_en': 'The Block',     'lang': 'en', 'url': 'https://www.theblock.co/rss.xml'},
        {'name': 'Blockworks',   'name_en': 'Blockworks',    'lang': 'en', 'url': 'https://blockworks.co/feed'},
        {'name': 'The Defiant',  'name_en': 'The Defiant',   'lang': 'en', 'url': 'https://thedefiant.io/api/rss'},
        {'name': 'CoinTelegraph','name_en': 'CoinTelegraph', 'lang': 'en', 'url': 'https://cointelegraph.com/rss'},
    ],

    'economy': [
        {'name': 'CBS财经',    'name_en': 'CBS MoneyWatch',  'lang': 'en', 'url': 'https://www.cbsnews.com/latest/rss/moneywatch'},
        {'name': 'CNBC',       'name_en': 'CNBC',            'lang': 'en', 'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html'},
        {'name': 'Forbes商业', 'name_en': 'Forbes Business', 'lang': 'en', 'url': 'https://www.forbes.com/business/feed/'},
        {'name': 'Yahoo财经',  'name_en': 'Yahoo Finance',   'lang': 'en', 'url': 'https://finance.yahoo.com/news/rssindex'},
        {'name': 'MarketWatch','name_en': 'MarketWatch',     'lang': 'en', 'url': 'https://feeds.content.dowjones.io/public/rss/mw_topstories'},
    ],
}


def _extract_image(entry):
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            url = m.get('url', '')
            t   = m.get('type', '')
            if url and (t.startswith('image') or
                        url.lower().split('?')[0].endswith(('.jpg','.jpeg','.png','.webp','.gif'))):
                return url
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url', '')
        if url:
            return url
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image'):
                return enc.get('href') or enc.get('url', '')
    for attr in ('summary', 'description'):
        html = getattr(entry, attr, '') or ''
        if '<img' in html:
            m = re.search(r'<img[^>]+src=["\']([^"\']{10,})["\']', html, re.I)
            if m:
                return m.group(1)
    if hasattr(entry, 'content') and entry.content:
        for c in entry.content:
            html = c.get('value', '')
            if '<img' in html:
                m = re.search(r'<img[^>]+src=["\']([^"\']{10,})["\']', html, re.I)
                if m:
                    return m.group(1)
    return None


def _clean(html_text, max_len=280):
    if not html_text:
        return ''
    text = BeautifulSoup(html_text, 'html.parser').get_text(separator=' ')
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + '…'
    return text


def _fetch_source(source, limit=20):
    articles = []
    try:
        feed = feedparser.parse(source['url'], request_headers=HEADERS)
        for entry in feed.entries[:limit]:
            title = getattr(entry, 'title', '').strip()
            if not title:
                continue
            raw = (getattr(entry, 'summary', '')
                   or getattr(entry, 'description', '') or '')
            articles.append({
                'title':      title,
                'summary':    _clean(raw),
                'summary_zh': '',   # 由 translator 填充
                'summary_en': '',   # 由 translator 填充
                'link':       getattr(entry, 'link', '#'),
                'image':      _extract_image(entry),
                'source':     source['name'],
                'source_en':  source.get('name_en', source['name']),
                'lang':       source.get('lang', 'en'),
                'published':  getattr(entry, 'published', ''),
            })
        logger.debug(f"  [{source['name']}] {len(articles)} 篇")
    except Exception as e:
        logger.warning(f"  [{source['name']}] 抓取失败: {e}")
    return articles


def _deduplicate(articles):
    seen, unique = set(), []
    for a in articles:
        key = a['title'][:40].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


# 最终展示条数上限（main.py 在去重后截取）
DISPLAY_LIMITS = {
    'world':   6,
    'ai':      5,
    'crypto':  5,
    'economy': 8,
}


def fetch_all_news(max_per_category=5):
    """
    抓取所有类别新闻，返回完整的原始池（每来源最多20条）。
    跨日去重和最终截取在 main.py 完成，确保去重后仍有足够新文章填满版面。
    """
    all_news = {}
    for category, sources in RSS_SOURCES.items():
        pool = []
        for src in sources:
            fetched = _fetch_source(src, limit=20)  # 每源最多20条，RSS通常有10-30条
            pool.extend(fetched)

        pool = _deduplicate(pool)  # 仅去除本次抓取内的重复

        # 加密货币：PA News (lang=zh) 优先排前面
        if category == 'crypto':
            pa   = [a for a in pool if a['lang'] == 'zh']
            rest = [a for a in pool if a['lang'] != 'zh']
            pool = pa + rest

        all_news[category] = pool
        logger.info(f"[{category}] 抓取原始池 {len(pool)} 篇（跨日去重前）")

    return all_news
