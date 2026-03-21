"""
邮件发送模块 — HTML 正文（含新闻摘要）+ PDF 附件
PDF 为去除 base64 图表的精简版，体积 ~10-15 MB，不超出 Gmail 限制
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)

SITE_URL = 'https://zerlindamazz-droid.github.io/daily-news-report/'

SECTION_LABELS = {
    'world':   ('🌍 全球要闻',   'World News'),
    'ai':      ('🤖 AI 科技',    'AI & Tech'),
    'crypto':  ('₿ 加密货币',    'Crypto'),
    'economy': ('📈 全球经济',   'Economy'),
}


def _article_html(article):
    title_zh = article.get('title_zh') or article.get('title', '')
    title_en = article.get('title_en') or article.get('title', '')
    summary_zh = article.get('summary_zh') or ''
    summary_en = article.get('summary_en') or ''
    source = article.get('source', '')
    link   = article.get('link', '#')
    published = (article.get('published') or '')[:10]

    return f'''
<tr>
  <td style="padding:12px 0;border-bottom:1px solid #eef0f4;">
    <div style="font-size:13px;color:#6b7280;margin-bottom:4px;">
      {source}{(' · ' + published) if published else ''}
    </div>
    <a href="{link}" style="font-size:16px;font-weight:600;color:#1d4ed8;text-decoration:none;line-height:1.4;display:block;">
      {title_zh}
    </a>
    <div style="font-size:13px;color:#6b7280;margin-top:2px;">{title_en}</div>
    {f'<div style="font-size:14px;color:#374151;margin-top:6px;line-height:1.5;">{summary_zh}</div>' if summary_zh else ''}
  </td>
</tr>'''


def send_report_email(email_cfg, date_str, la_time, news_data=None, pdf_path=None):
    """
    发送每日报告邮件（HTML 正文 + PDF 附件）

    参数:
        email_cfg : config["email"] 字典
        date_str  : 中文日期字符串
        la_time   : 洛杉矶时间字符串
        news_data : 各板块新闻 dict
        pdf_path  : 精简版 PDF 路径（已去除 base64 图表，~10-15 MB）
    """
    sender   = email_cfg['sender']
    password = email_cfg['password']
    host     = email_cfg.get('smtp_host', 'smtp.gmail.com')
    port     = email_cfg.get('smtp_port', 587)

    raw = email_cfg.get('recipients') or email_cfg.get('recipient')
    recipients = raw if isinstance(raw, list) else [raw]

    subject = f'📰 每日全球要闻 — {date_str}'

    # ── 构建各板块 HTML ────────────────────────────────────────────
    sections_html = ''
    for cat in ('world', 'economy', 'ai', 'crypto'):
        articles = (news_data or {}).get(cat, [])
        if not articles:
            continue
        label_zh, label_en = SECTION_LABELS.get(cat, (cat, cat))
        rows = ''.join(_article_html(a) for a in articles)
        sections_html += f'''
<tr>
  <td style="padding:20px 0 8px;">
    <div style="font-size:18px;font-weight:700;color:#111827;border-left:4px solid #1d4ed8;padding-left:10px;">
      {label_zh} <span style="font-size:13px;font-weight:400;color:#9ca3af;">/ {label_en}</span>
    </div>
  </td>
</tr>
{rows}'''

    body_html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
  <tr><td>
    <table width="620" align="center" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 8px rgba(0,0,0,.08);">

      <!-- header -->
      <tr><td style="background:#1d4ed8;padding:24px 32px;">
        <div style="font-size:22px;font-weight:700;color:#fff;">📰 每日全球要闻快报</div>
        <div style="font-size:14px;color:#bfdbfe;margin-top:4px;">
          {date_str} &nbsp;·&nbsp; 洛杉矶 {la_time}
        </div>
      </td></tr>

      <!-- body -->
      <tr><td style="padding:8px 32px 24px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          {sections_html}
        </table>
      </td></tr>

      <!-- footer -->
      <tr><td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb;">
        <div style="font-size:13px;color:#6b7280;text-align:center;">
          查看完整报告（含图表）：
          <a href="{SITE_URL}" style="color:#1d4ed8;font-weight:600;">{SITE_URL}</a>
        </div>
      </td></tr>

    </table>
  </td></tr>
</table>
</body></html>'''

    msg = MIMEMultipart('mixed')
    msg['From']    = sender
    msg['To']      = ', '.join(recipients)
    msg['Subject'] = subject

    # HTML 正文
    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(body_html, 'html', 'utf-8'))
    msg.attach(alt)

    # PDF 附件（精简版，已去除 base64 图表）
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        attachment = MIMEApplication(pdf_data, _subtype='pdf')
        filename = f'daily_report_{date_str}.pdf'
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attachment)
        logger.info(f"PDF 附件: {filename} ({len(pdf_data)//1024} KB)")
    else:
        logger.warning("未找到 PDF，仅发送 HTML 正文")

    logger.info(f"正在连接 {host}:{port} …")
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(sender, password)
        smtp.sendmail(sender, recipients, msg.as_bytes())

    logger.info(f"邮件已成功发送至: {', '.join(recipients)}")
