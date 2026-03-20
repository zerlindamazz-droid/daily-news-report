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

    # ── 去重：按 URL + 标题 过滤过去7天已出现的新闻 ──────────────────
    seen_path = out_dir / 'seen_links.json'
    try:
        import json as _json
        from datetime import timedelta

        seen_data = _json.loads(seen_path.read_text(encoding='utf-8')) if seen_path.exists() else {}
        cutoff = (now - timedelta(days=7)).strftime('%Y-%m-%d')
        seen_data = {k: v for k, v in seen_data.items() if v >= cutoff}
        # 只过滤"昨天及之前"出现过的新闻，今天的条目不参与过滤
        # 这样同一天多次生成报告不会把当天的新闻全部挡掉
        seen_keys = {k for k, v in seen_data.items() if v < date_tag}

        def _title_key(title):
            """标题归一化 key（小写+去空格，取前60字符）"""
            return ''.join(title.lower().split())[:60]

        total_before = sum(len(v) for v in news_data.values())
        for cat in news_data:
            filtered = []
            for a in news_data[cat]:
                url = a.get('link', '')
                tk  = _title_key(a.get('title', ''))
                if url in seen_keys or tk in seen_keys:
                    continue
                filtered.append(a)
            news_data[cat] = filtered
        total_after = sum(len(v) for v in news_data.values())
        logger.info(f"去重完成：过滤 {total_before - total_after} 条已出现过的新闻，剩余 {total_after} 条")

        # 每来源最多保留2条，保证来源多样性
        # crypto 板块例外：PA News 最多保留4条，其余来源最多1条
        for cat in news_data:
            source_count: dict = {}
            diverse = []
            for a in news_data[cat]:
                src = a.get('source', '')
                if cat == 'crypto' and src == 'PA News':
                    limit_src = 4
                elif cat == 'crypto':
                    limit_src = 1
                else:
                    limit_src = 2
                if source_count.get(src, 0) < limit_src:
                    diverse.append(a)
                    source_count[src] = source_count.get(src, 0) + 1
            news_data[cat] = diverse

        # 去重后截取到展示上限
        from news_fetcher import DISPLAY_LIMITS
        display_limits = {'world': 6, 'ai': max_art, 'crypto': max_art, 'economy': 8}
        display_limits.update(DISPLAY_LIMITS)
        for cat, limit in display_limits.items():
            if cat in news_data:
                news_data[cat] = news_data[cat][:limit]
        total_display = sum(len(v) for v in news_data.values())
        logger.info(f"截取后：共展示 {total_display} 条新闻")

        # 记录本次新闻的 URL 和标题 key
        for cat in news_data:
            for a in news_data[cat]:
                if a.get('link'):
                    seen_data[a['link']] = date_tag
                tk = _title_key(a.get('title', ''))
                if tk:
                    seen_data[tk] = date_tag
        seen_path.write_text(_json.dumps(seen_data, ensure_ascii=False, indent=2), encoding='utf-8')
        logger.info(f"seen_links.json 已更新，共 {len(seen_data)} 条记录")
    except Exception as e:
        logger.warning(f"去重处理失败（跳过）: {e}")

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

    # ── 转换 PDF（去除 base64 图片以缩小体积，避免超出 Gmail 25MB 限制）──
    pdf_ok = False
    try:
        import re as _re
        slim_html = html_path.read_text(encoding='utf-8')
        # 将 base64 内嵌图片替换为空（图表在网站上可见，邮件 PDF 不含图表）
        slim_html = _re.sub(
            r'<img\s+src="data:image/[^"]+"\s*[^>]*>',
            '<p style="color:#888;font-size:12px;text-align:center;">[图表请在网站查看]</p>',
            slim_html,
        )
        slim_path = html_path.parent / f'_slim_{html_path.name}'
        slim_path.write_text(slim_html, encoding='utf-8')
        html_to_pdf(slim_path, pdf_path)
        slim_path.unlink(missing_ok=True)
        pdf_size_kb = pdf_path.stat().st_size // 1024
        logger.info(f"PDF 生成完成，大小 {pdf_size_kb} KB")
        pdf_ok = True
    except Exception as e:
        logger.error(f"PDF 转换失败: {e}")
        logger.info("将直接发送不含 PDF 附件的邮件")

    # ── 生成 index.html = 今日报告 + 历史面板 ────────────────────────
    try:
        import glob as _glob
        from pathlib import Path as _Path
        reports = sorted(_glob.glob(str(out_dir / 'report_*.html')), reverse=True)

        # 构建历史报告列表 HTML
        history_items = ''
        for rpt in reports:
            p = _Path(rpt)
            d = p.name.replace('report_', '').replace('.html', '')
            active = 'style="font-weight:700;color:#1d4ed8;"' if p.name == html_path.name else ''
            history_items += f'<li><a href="{p.name}" {active}>{d}</a></li>'

        history_widget = f'''
<div id="hist-wrap" style="position:fixed;bottom:24px;left:24px;z-index:1000;font-family:Inter,sans-serif;">
  <button onclick="var p=document.getElementById('hist-box');p.style.display=p.style.display==='none'?'block':'none'"
    style="background:#1d4ed8;color:#fff;border:none;border-radius:8px;padding:8px 18px;font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.2);">
    📅 历史报告
  </button>
  <div id="hist-box" style="display:none;background:#fff;border:1px solid #e2e8f0;border-radius:10px;
    box-shadow:0 4px 20px rgba(0,0,0,.12);padding:12px 16px;margin-top:6px;max-height:320px;overflow-y:auto;min-width:160px;">
    <ul style="list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px;">
      {history_items}
    </ul>
  </div>
</div>'''

        # index.html = 今日报告内容 + 历史面板（插在 </body> 前）
        index_html = html_content.replace('</body>', history_widget + '\n</body>')
        (out_dir / 'index.html').write_text(index_html, encoding='utf-8')
        logger.info("index.html 已生成（今日报告 + 历史面板）")
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
                news_data  = news_data,
            )
        except Exception as e:
            logger.error(f"邮件发送失败: {e}\n{traceback.format_exc()}")
            # 邮件失败不中断流程，报告已生成并将正常部署

    logger.info("全部完成！")
    logger.info("=" * 60)
    return True


if __name__ == '__main__':
    success = run()
    sys.exit(0 if success else 1)
