"""
邮件发送模块
使用 Gmail SMTP 发送带 PDF 附件的 HTML 邮件
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)


def send_report_email(email_cfg, date_str, la_time, pdf_path):
    """
    发送每日报告邮件

    参数:
        email_cfg  : config["email"] 字典
        date_str   : 日期字符串，例如 "2024年3月12日 星期二"
        la_time    : 时间字符串，例如 "07:30"
        pdf_path   : PDF 文件路径
    """
    sender   = email_cfg['sender']
    password = email_cfg['password']
    host     = email_cfg.get('smtp_host', 'smtp.gmail.com')
    port     = email_cfg.get('smtp_port', 587)

    # 支持单个字符串或列表两种格式
    raw = email_cfg.get('recipients') or email_cfg.get('recipient')
    recipients = raw if isinstance(raw, list) else [raw]

    subject = f'📰 每日全球要闻快报 — {date_str}'

    body_html = f"""
    <html><body style="font-family:'Microsoft YaHei',sans-serif;background:#0d0d1a;color:#e2e2f0;padding:30px;">
      <div style="max-width:560px;margin:0 auto;text-align:center;">
        <h2 style="color:#f0a500;">📰 每日全球要闻快报</h2>
        <p style="color:#8888aa;">洛杉矶时间 <strong style="color:#fff;">{la_time}</strong>
           &nbsp;·&nbsp; <strong style="color:#fff;">{date_str}</strong></p>
        <p style="margin-top:20px;">您好，请查看附件中的 <strong>今日完整报告（PDF）</strong>。</p>
        <p style="margin-top:10px;color:#555577;font-size:12px;">
          内容涵盖：全球要闻 · AI科技 · 加密货币 · 全球股市
        </p>
      </div>
    </body></html>
    """

    msg = MIMEMultipart('mixed')
    msg['From']    = sender
    msg['To']      = ', '.join(recipients)
    msg['Subject'] = subject

    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    # 附加 PDF
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        attachment = MIMEApplication(pdf_data, _subtype='pdf')
        filename = f'daily_report_{date_str.replace(" ", "_")}.pdf'
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attachment)
        logger.info(f"PDF 附件: {filename} ({len(pdf_data)//1024} KB)")
    else:
        logger.warning("未找到 PDF 文件，将发送不含附件的邮件")

    # 发送给所有收件人
    logger.info(f"正在连接 {host}:{port} …")
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(sender, password)
        smtp.sendmail(sender, recipients, msg.as_bytes())

    logger.info(f"邮件已成功发送至: {', '.join(recipients)}")
