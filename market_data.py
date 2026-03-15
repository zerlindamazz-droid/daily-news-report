"""
市场数据模块
- 从 CoinGecko 获取加密货币实时价格
- 从 yfinance 获取全球主要股票指数
- 生成 matplotlib 图表（Base64 编码内嵌到 HTML）
"""

import io
import base64
import logging
import requests
import yfinance as yf
from datetime import datetime
import pytz
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，必须在 import pyplot 之前设置
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

logger = logging.getLogger(__name__)

# ─── 字体配置（中文支持）──────────────────────────────────────────────────────
def _setup_chinese_font():
    """配置 matplotlib 中文字体"""
    candidates = ['Microsoft YaHei', 'SimHei', 'SimSun', 'FangSong', 'KaiTi',
                  'Noto Sans CJK SC', 'Noto Sans SC', 'Noto Sans CJK JP',
                  'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'DejaVu Sans']
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams['font.sans-serif'] = [font] + plt.rcParams.get('font.sans-serif', [])
            plt.rcParams['axes.unicode_minus'] = False
            logger.debug(f"使用字体: {font}")
            return
    plt.rcParams['axes.unicode_minus'] = False

_setup_chinese_font()

# ─── 数据配置 ─────────────────────────────────────────────────────────────────
CRYPTO_LIST = [
    ('bitcoin',       'BTC',  '比特币'),
    ('ethereum',      'ETH',  '以太坊'),
    ('solana',        'SOL',  '索拉纳'),
    ('binancecoin',   'BNB',  '币安币'),
    ('ripple',        'XRP',  'XRP'),
    ('cardano',       'ADA',  '卡尔达诺'),
    ('dogecoin',      'DOGE', '狗狗币'),
    ('avalanche-2',   'AVAX', '雪崩'),
]

STOCK_INDICES = [
    ('^GSPC',    '标普500',   'S&P 500'),
    ('^IXIC',    '纳斯达克',  'NASDAQ'),
    ('^DJI',     '道琼斯',    'Dow Jones'),
    ('^FTSE',    '富时100',   'FTSE 100'),
    ('^GDAXI',   '德国DAX',   'DAX'),
    ('^N225',    '日经225',   'Nikkei 225'),
    ('000001.SS','上证指数',   'SSE Composite'),
    ('^HSI',     '恒生指数',  'Hang Seng'),
]

COINGECKO_URL = 'https://api.coingecko.com/api/v3/simple/price'

# ─── 数据获取 ─────────────────────────────────────────────────────────────────

def get_crypto_prices():
    """从 CoinGecko 获取加密货币价格"""
    try:
        ids = ','.join(c[0] for c in CRYPTO_LIST)
        params = {
            'ids': ids,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
            'include_7d_change': 'true',
            'include_market_cap': 'true',
        }
        headers = {'Accept': 'application/json'}
        resp = requests.get(COINGECKO_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        fetched_at = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M UTC')
        result = []
        for coin_id, symbol, name_cn in CRYPTO_LIST:
            if coin_id not in data:
                continue
            c = data[coin_id]
            result.append({
                'symbol':     symbol,
                'name_cn':    name_cn,
                'price':      c.get('usd', 0),
                'change_24h': c.get('usd_24h_change', 0) or 0,
                'change_7d':  c.get('usd_7d_change', 0) or 0,
                'market_cap': c.get('usd_market_cap', 0) or 0,
                'fetched_at': fetched_at,
            })
        logger.info(f"加密货币数据：获取 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"加密货币数据获取失败: {e}")
        return []


def get_stock_indices():
    """从 yfinance 获取全球主要股指"""
    indices = []
    for ticker, name_cn, name_en in STOCK_INDICES:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period='5d', interval='1d')
            if hist.empty or len(hist) < 1:
                continue
            current = float(hist['Close'].iloc[-1])
            prev    = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else current
            change     = current - prev
            change_pct = (change / prev * 100) if prev else 0
            date_str = hist.index[-1].strftime('%m/%d')
            indices.append({
                'ticker':     ticker,
                'name_cn':    name_cn,
                'name_en':    name_en,
                'value':      current,
                'change':     change,
                'change_pct': change_pct,
                'date':       date_str,
            })
        except Exception as e:
            logger.warning(f"股指 {ticker} 获取失败: {e}")

    logger.info(f"股票指数：获取 {len(indices)} 条")
    return indices

# ─── 图表生成 ─────────────────────────────────────────────────────────────────

_BG_DARK  = '#0f0f1a'
_BG_CARD  = '#16213e'
_GREEN    = '#00e676'
_RED      = '#ff5252'
_WHITE    = '#e8e8f0'
_GRAY     = '#555577'


def _fig_to_b64(fig):
    """将 matplotlib 图表保存为 Base64 PNG 字符串"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return b64


def generate_crypto_chart(crypto_prices):
    """生成加密货币 24h 涨跌柱状图"""
    if not crypto_prices:
        return None

    labels  = [p['symbol'] for p in crypto_prices]
    changes = [p['change_24h'] for p in crypto_prices]
    colors  = [_GREEN if c >= 0 else _RED for c in changes]

    fig, ax = plt.subplots(figsize=(11, 4))
    fig.patch.set_facecolor(_BG_DARK)
    ax.set_facecolor(_BG_CARD)

    bars = ax.bar(labels, changes, color=colors, alpha=0.88,
                  edgecolor='#ffffff22', linewidth=0.5)

    for bar, val in zip(bars, changes):
        y = bar.get_height()
        offset = 0.12 if val >= 0 else -0.35
        ax.text(bar.get_x() + bar.get_width() / 2,
                y + offset,
                f'{val:+.1f}%',
                ha='center', va='bottom',
                color=_WHITE, fontsize=8.5, fontweight='bold')

    ax.axhline(0, color=_GRAY, linewidth=0.8)
    ax.set_ylabel('24小时涨跌幅 (%)', color=_WHITE, fontsize=10)
    ax.set_title('加密货币 24 小时表现', color=_WHITE, fontsize=13,
                 fontweight='bold', pad=14)
    ax.tick_params(colors=_WHITE, labelsize=9)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('bottom', 'left'):
        ax.spines[spine].set_color(_GRAY)

    plt.tight_layout()
    return _fig_to_b64(fig)


def generate_market_chart(indices):
    """生成全球股指涨跌柱状图"""
    if not indices:
        return None

    labels  = [i['name_cn'] for i in indices]
    changes = [i['change_pct'] for i in indices]
    colors  = [_GREEN if c >= 0 else _RED for c in changes]

    fig, ax = plt.subplots(figsize=(11, 4))
    fig.patch.set_facecolor(_BG_DARK)
    ax.set_facecolor(_BG_CARD)

    bars = ax.bar(labels, changes, color=colors, alpha=0.88,
                  edgecolor='#ffffff22', linewidth=0.5)

    for bar, val in zip(bars, changes):
        y = bar.get_height()
        offset = 0.03 if val >= 0 else -0.12
        ax.text(bar.get_x() + bar.get_width() / 2,
                y + offset,
                f'{val:+.2f}%',
                ha='center', va='bottom',
                color=_WHITE, fontsize=8.5, fontweight='bold')

    ax.axhline(0, color=_GRAY, linewidth=0.8)
    ax.set_ylabel('涨跌幅 (%)', color=_WHITE, fontsize=10)
    ax.set_title('全球主要股指表现', color=_WHITE, fontsize=13,
                 fontweight='bold', pad=14)
    ax.tick_params(colors=_WHITE, labelsize=9)
    plt.xticks(rotation=25, ha='right')
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    for spine in ('bottom', 'left'):
        ax.spines[spine].set_color(_GRAY)

    plt.tight_layout()
    return _fig_to_b64(fig)


def get_all_market_data():
    """获取所有市场数据并生成图表"""
    logger.info("开始获取市场数据…")
    crypto_prices  = get_crypto_prices()
    stock_indices  = get_stock_indices()
    crypto_chart   = generate_crypto_chart(crypto_prices)
    market_chart   = generate_market_chart(stock_indices)

    crypto_fetched_at = crypto_prices[0]['fetched_at'] if crypto_prices else ''

    return {
        'crypto_prices':    crypto_prices,
        'stock_indices':    stock_indices,
        'crypto_chart_b64': crypto_chart,
        'market_chart_b64': market_chart,
        'crypto_fetched_at': crypto_fetched_at,
    }
