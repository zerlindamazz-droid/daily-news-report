"""
每日全球要闻快报 — 主程序
运行逻辑:
  1. 从 RSS 抓取全球要闻、AI、加密、经济新闻
  2. 从 CoinGecko / yfinance 获取市场实时数据并生成图表
  3. 渲染 HTML 报告并保存
  4. 用 Playwright 将 HTML 转换为 PDF
  5. 通过 Gmail SMTP 将 PDF 发送到配置的邮箱
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

import pytz

# ─── 日志配置 ─────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'report.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger('main')

# ─── 路径 ──────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
CONFIG_PATH = BASE_DIR / 'config.json'


def load_config():
    """加载配置，config.json 不存在时使用默认结构（依赖环境变量）"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    # GitHub Actions 环境：config.json 不存在，返回空壳，由环境变量填充
    return {
        'email': {'sender': '', 'password': '', 'recipients': [],
                  'smtp_host': 'smtp.gmail.com', 'smtp_port': 587},
        'report': {'timezone': 'America/Los_Angeles', 'max_articles': 5, 'output_dir': 'output'}
    }


def html_to_pdf(html_path: Path, pdf_path: Path):
    """使用 Playwright 将 HTML 文件转换为 PDF"""
    from playwright.sync_api import sync_playwright

    logger.info("启动 Playwright 转换 HTML → PDF …")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # 加载本地 HTML 文件
        page.goto(f'file:///{html_path.as_posix()}', wait_until='networkidle', timeout=30000)
        # 等待图片加载
        page.wait_for_timeout(3000)
        page.pdf(
            path=str(pdf_path),
            format='A4',
            print_background=True,
            margin={'top': '12mm', 'bottom': '12mm', 'left': '10mm', 'right': '10mm'},
        )
        browser.close()
    logger.info(f"PDF 已保存: {pdf_path}")


def run():
    """执行完整的报告生成和发送流程"""
    logger.info("=" * 60)
    logger.info("开始生成每日报告 …")

    # ── 加载配置 ──────────────────────────────────────────────────
    try:
        config = load_config()
    except Exception:
        logger.error("无法读取 config.json，请先填写配置文件")
        return False

    # 用环境变量覆盖配置（GitHub Actions 场景）
    email_cfg = config['email']
    if os.getenv('GMAIL_SENDER'):
        email_cfg['sender'] = os.getenv('GMAIL_SENDER')
    if os.getenv('GMAIL_PASSWORD'):
        email_cfg['password'] = os.getenv('GMAIL_PASSWORD')
    if os.getenv('GMAIL_RECIPIENTS'):
        email_cfg['recipients'] = [r.strip() for r in os.getenv('GMAIL_RECIPIENTS').split(',')]

    # 校验
    if not email_cfg.get('sender'):
        logger.error("邮件配置缺失：请填写 config.json 或设置 GMAIL_SENDER 环境变量")
        return False

    report_cfg = config.get('report', {})
    tz_name    = report_cfg.get('timezone', 'America/Los_Angeles')
    max_art    = report_cfg.get('max_articles', 5)
    out_dir    = BASE_DIR / report_cfg.get('output_dir', 'output')
    out_dir.mkdir(exist_ok=True)

    # 日期用于文件名
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    date_tag = now.strftime('%Y-%m-%d')

    html_path = out_dir / f'report_{date_tag}.html'
    pdf_path  = out_dir / f'report_{date_tag}.pdf'

    # ── 抓取新闻 ──────────────────────────────────────────────────
    try:
        from news_fetcher import fetch_all_news
        logger.info("正在抓取各类新闻 …")
        news_data = fetch_all_news(max_per_category=max_art)
    except Exception as e:
        logger.error(f"新闻抓取失败: {e}\n{traceback.format_exc()}")
        news_data = {'world': [], 'ai': [], 'crypto': [], 'economy': []}

    # ── 生成双语摘要 ───────────────────────────────────────────────
    try:
        from translator import enrich_articles_with_bilingual_summary
        logger.info("正在生成双语摘要（Google翻译）…")
        enrich_articles_with_bilingual_summary(news_data)
    except Exception as e:
        logger.warning(f"双语摘要生成失败，将使用原文摘要: {e}")
        # 回退：原文同时赋给 zh 和 en
        for articles in news_data.values():
            for a in articles:
                a.setdefault('summary_zh', a.get('summary', ''))
                a.setdefault('summary_en', a.get('summary', ''))

    # ── 获取市场数据 ───────────────────────────────────────────────
    try:
        from market_data import get_all_market_data
        market_data = get_all_market_data()
    except Exception as e:
        logger.error(f"市场数据获取失败: {e}\n{traceback.format_exc()}")
        market_data = {'crypto_prices': [], 'stock_indices': [],
                       'crypto_chart_b64': None, 'market_chart_b64': None}

    # ── 渲染 HTML 报告 ─────────────────────────────────────────────
    try:
        from report_generator import generate_html_report
        html_content, date_str, la_time = generate_html_report(
            news_data, market_data, timezone=tz_name
        )
        html_path.write_text(html_content, encoding='utf-8')
        logger.info(f"HTML 报告已保存: {html_path}")
    except Exception as e:
        logger.error(f"HTML 生成失败: {e}\n{traceback.format_exc()}")
        return False

    # ── 转换 PDF ───────────────────────────────────────────────────
    pdf_ok = False
    try:
        html_to_pdf(html_path, pdf_path)
        pdf_ok = True
    except Exception as e:
        logger.error(f"PDF 转换失败（需要 playwright install chromium）: {e}")
        logger.info("将直接发送不含 PDF 附件的邮件")

    # ── 生成静态 index.html（GitHub Pages 首页）──────────────────────
    try:
        import glob as _glob
        reports = sorted(_glob.glob(str(out_dir / 'report_*.html')), reverse=True)
        rows = ''
        for rpt in reports:
            from pathlib import Path as _Path
            p = _Path(rpt)
            d = p.name.replace('report_','').replace('.html','')
            kb = p.stat().st_size // 1024
            rows += f'<tr><td><a href="{p.name}">{d}</a></td><td style="color:#555577">{kb} KB</td></tr>'
        latest = Path(reports[0]).name if reports else ''
        redirect = f'<meta http-equiv="refresh" content="0; url={latest}">' if latest else ''
        index_html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">{redirect}
<title>每日全球要闻快报</title>
<style>body{{font-family:"Microsoft YaHei",sans-serif;background:#0d0d1a;color:#e2e2f0;padding:40px;}}
h1{{color:#f0a500;}}a{{color:#3d86f5;}}table{{border-collapse:collapse;width:100%;max-width:500px;}}
td{{padding:10px 16px;border-bottom:1px solid #2a2a50;}}
.btn{{display:inline-block;background:#f0a500;color:#000;font-weight:700;padding:12px 32px;border-radius:8px;text-decoration:none;margin:20px 0;}}
</style></head><body>
<h1>📰 每日全球要闻快报</h1>
{"<a class='btn' href='"+latest+"'>查看今日报告 →</a>" if latest else "<p>暂无报告</p>"}
<h2 style="color:#8888aa;font-size:14px;margin-top:30px">历史报告</h2>
<table>{rows}</table>
<p style="color:#555577;font-size:12px;margin-top:30px">每天洛杉矶 07:30 自动更新 · 数据来源：Reuters · BBC · PA News · CoinGecko</p>
</body></html>'''
        (out_dir / 'index.html').write_text(index_html, encoding='utf-8')
        logger.info("静态 index.html 已生成")
    except Exception as e:
        logger.warning(f"index.html 生成失败: {e}")

    # ── 发送邮件 ───────────────────────────────────────────────────
    if os.getenv('SKIP_EMAIL', '').lower() in ('1', 'true', 'yes'):
        logger.info("SKIP_EMAIL=true，跳过邮件发送")
    else:
        try:
            from email_sender import send_report_email
            send_report_email(
                email_cfg  = email_cfg,
                date_str   = date_str,
                la_time    = la_time,
                pdf_path   = pdf_path if pdf_ok else None,
            )
        except Exception as e:
            logger.error(f"邮件发送失败: {e}\n{traceback.format_exc()}")
            return False

    logger.info("全部完成！")
    logger.info("=" * 60)
    return True


if __name__ == '__main__':
    success = run()
    sys.exit(0 if success else 1)
