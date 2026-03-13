"""
本地 Web 服务器
访问 http://localhost:8080 查看最新报告
访问 http://localhost:8080/archive 查看历史报告列表
"""

import os
import sys
import glob
import logging
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

PORT = 8080
BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / 'output'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [WebServer] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / 'logs' / 'webserver.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger('webserver')


def _get_all_reports():
    """返回所有 HTML 报告，按日期降序排列"""
    files = sorted(
        glob.glob(str(OUTPUT_DIR / 'report_*.html')),
        reverse=True
    )
    return [Path(f) for f in files]


def _index_page():
    """生成报告列表首页 HTML"""
    reports = _get_all_reports()

    if reports:
        latest_name = reports[0].name
        latest_date = latest_name.replace('report_', '').replace('.html', '')
        latest_link = f'/{latest_name}'
        latest_block = f'''
        <div class="latest-card">
          <div class="latest-label">最新报告</div>
          <div class="latest-date">{latest_date}</div>
          <a href="{latest_link}" class="btn-view">立即查看 →</a>
        </div>'''
    else:
        latest_block = '<div class="no-report">尚无报告，请等待明天 07:30 自动生成，或手动运行 run.bat</div>'

    rows = ''
    for rpt in reports:
        name = rpt.name
        date = name.replace('report_', '').replace('.html', '')
        size_kb = rpt.stat().st_size // 1024
        pdf_name = name.replace('.html', '.pdf')
        pdf_path = OUTPUT_DIR / pdf_name
        pdf_link = f'<a href="/{pdf_name}" class="dl-pdf">下载 PDF</a>' if pdf_path.exists() else ''
        rows += f'''
        <tr>
          <td><a href="/{name}">{date}</a></td>
          <td class="muted">{size_kb} KB</td>
          <td>{pdf_link}</td>
        </tr>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="300">
<title>每日全球要闻快报</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#0d0d1a;color:#e2e2f0;min-height:100vh}}
  .header{{background:linear-gradient(135deg,#0a0a1e,#1a1040);border-bottom:2px solid #f0a500;padding:32px 20px;text-align:center}}
  .header h1{{font-size:28px;color:#fff}} .header h1 span{{color:#f0a500}}
  .header p{{color:#8888aa;margin-top:8px;font-size:13px}}
  .container{{max-width:800px;margin:0 auto;padding:30px 20px}}
  .latest-card{{background:#14142a;border:1px solid #f0a500;border-radius:12px;padding:28px 32px;text-align:center;margin-bottom:36px}}
  .latest-label{{font-size:11px;color:#f0a500;letter-spacing:3px;font-weight:700;margin-bottom:10px}}
  .latest-date{{font-size:22px;font-weight:700;color:#fff;margin-bottom:18px}}
  .btn-view{{display:inline-block;background:#f0a500;color:#000;font-weight:700;padding:12px 36px;border-radius:8px;text-decoration:none;font-size:15px}}
  .btn-view:hover{{background:#ffd166}}
  .no-report{{color:#8888aa;text-align:center;padding:20px;background:#14142a;border-radius:10px;margin-bottom:30px}}
  h2{{font-size:16px;color:#8888aa;letter-spacing:2px;margin-bottom:16px;font-weight:400}}
  table{{width:100%;border-collapse:collapse;background:#14142a;border-radius:10px;overflow:hidden}}
  th{{background:#1c1c38;color:#f0a500;font-size:12px;letter-spacing:1px;padding:12px 16px;text-align:left}}
  td{{padding:11px 16px;border-bottom:1px solid #2a2a50;font-size:14px}}
  td a{{color:#3d86f5;text-decoration:none}} td a:hover{{text-decoration:underline}}
  .muted{{color:#555577}}
  .dl-pdf{{color:#00e676;font-size:12px}}
  .status{{background:#14142a;border:1px solid #2a2a50;border-radius:8px;padding:14px 18px;margin-top:24px;font-size:12px;color:#555577;text-align:center}}
  .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;background:#00e676;margin-right:8px;animation:pulse 2s infinite}}
  @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
</style>
</head>
<body>
<div class="header">
  <h1>每日全球<span>要闻</span>快报</h1>
  <p>全球重大事件 · AI科技 · 加密货币 · 全球股市 &nbsp;|&nbsp; 每天洛杉矶 07:30 自动更新</p>
</div>
<div class="container">
  {latest_block}
  <h2>◆ 历史报告</h2>
  <table>
    <thead><tr><th>日期</th><th>文件大小</th><th>PDF下载</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="3" style="color:#555577;text-align:center;padding:20px">暂无历史报告</td></tr>'}</tbody>
  </table>
  <div class="status">
    <span class="dot"></span>服务运行中 &nbsp;·&nbsp; 端口 {PORT} &nbsp;·&nbsp; 页面每 5 分钟自动刷新
  </div>
</div>
</body>
</html>'''


class ReportHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # 静默HTTP请求日志，只保留错误
        pass

    def do_GET(self):
        path = unquote(self.path.lstrip('/'))

        # 根路径 → 首页
        if path == '' or path == 'index.html':
            self._serve_html(_index_page())
            return

        # 提供 HTML 或 PDF 文件
        target = OUTPUT_DIR / path
        if target.exists() and target.suffix in ('.html', '.pdf'):
            mime = 'text/html; charset=utf-8' if target.suffix == '.html' else 'application/pdf'
            with open(target, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        # 404
        self._serve_html('<h2 style="color:#ff5252;font-family:sans-serif;text-align:center;margin-top:100px">404 — 文件不存在</h2>', 404)

    def _serve_html(self, html, code=200):
        data = html.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    server = HTTPServer(('0.0.0.0', PORT), ReportHandler)
    logger.info(f"Web 服务已启动 → http://localhost:{PORT}")
    logger.info(f"局域网访问: 用你的电脑 IP 替换 localhost")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Web 服务已停止")


if __name__ == '__main__':
    main()
