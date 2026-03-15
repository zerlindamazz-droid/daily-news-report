"""
报告生成模块 — 双语版
将新闻数据、市场数据渲染成中英双语 HTML 报告
"""

import os
import pytz
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)
_DIR = os.path.dirname(os.path.abspath(__file__))
WEEKDAY_CN = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
WEEKDAY_EN = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

CATEGORY_LABELS = {
    'world':   ('全球', 'World'),
    'ai':      ('AI',  'AI'),
    'crypto':  ('加密', 'Crypto'),
    'economy': ('经济', 'Economy'),
}


def _build_key_points(news_data, market_data):
    """
    生成今日要点，返回 [{'zh': '...', 'en': '...'}, ...]
    """
    points = []

    # 全球头条
    world = news_data.get('world', [])
    if world:
        points.append({
            'zh': f"【全球】{world[0].get('title_zh') or world[0]['title']}",
            'en': f"[World] {world[0].get('title_en') or world[0]['title']}",
        })

    # AI 头条
    ai = news_data.get('ai', [])
    if ai:
        points.append({
            'zh': f"【AI】{ai[0].get('title_zh') or ai[0]['title']}",
            'en': f"[AI] {ai[0].get('title_en') or ai[0]['title']}",
        })

    # 加密货币
    crypto = market_data.get('crypto_prices', [])
    btc = next((c for c in crypto if c['symbol'] == 'BTC'), None)
    eth = next((c for c in crypto if c['symbol'] == 'ETH'), None)
    if btc or eth:
        parts_zh, parts_en = [], []
        for coin in [btc, eth]:
            if coin:
                sign = '▲' if coin['change_24h'] >= 0 else '▼'
                parts_zh.append(f"{coin['symbol']} {sign}{abs(coin['change_24h']):.1f}%")
                parts_en.append(f"{coin['symbol']} {sign}{abs(coin['change_24h']):.1f}%")
        if parts_zh:
            points.append({'zh': f"【加密】{' | '.join(parts_zh)}（24h 涨跌）",
                           'en': f"[Crypto] {' | '.join(parts_en)} (24h change)"})

    # 股市
    indices = market_data.get('stock_indices', [])
    sp500 = next((i for i in indices if i['ticker'] == '^GSPC'), None)
    if sp500:
        sign = '▲' if sp500['change_pct'] >= 0 else '▼'
        points.append({
            'zh': f"【股市】标普500 {sign}{abs(sp500['change_pct']):.2f}%，报 {sp500['value']:,.2f} 点",
            'en': f"[Markets] S&P 500 {sign}{abs(sp500['change_pct']):.2f}%, at {sp500['value']:,.2f}",
        })

    # 经济头条
    eco = news_data.get('economy', [])
    if eco:
        points.append({
            'zh': f"【经济】{eco[0].get('title_zh') or eco[0]['title']}",
            'en': f"[Economy] {eco[0].get('title_en') or eco[0]['title']}",
        })

    return points[:5]


def generate_html_report(news_data, market_data, timezone='America/Los_Angeles'):
    tz  = pytz.timezone(timezone)
    now = datetime.now(tz)

    date_str    = f"{now.year}年{now.month}月{now.day}日 {WEEKDAY_CN[now.weekday()]}"
    date_str_en = f"{WEEKDAY_EN[now.weekday()]}, {now.strftime('%B')} {now.day}, {now.year}"
    la_time     = now.strftime('%H:%M')

    key_points = _build_key_points(news_data, market_data)

    env = Environment(loader=FileSystemLoader(_DIR), autoescape=False)
    template = env.get_template('template.html')

    html = template.render(
        date_str        = date_str,
        date_str_en     = date_str_en,
        la_time         = la_time,
        key_points      = key_points,
        world_news      = news_data.get('world', []),
        ai_news         = news_data.get('ai', []),
        crypto_news     = news_data.get('crypto', []),
        economy_news    = news_data.get('economy', []),
        crypto_prices    = market_data.get('crypto_prices', []),
        stock_indices    = market_data.get('stock_indices', []),
        crypto_chart_b64 = market_data.get('crypto_chart_b64', ''),
        market_chart_b64 = market_data.get('market_chart_b64', ''),
        crypto_fetched_at= market_data.get('crypto_fetched_at', ''),
    )

    logger.info("HTML 报告生成完成")
    return html, date_str, la_time
