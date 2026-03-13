"""
定时调度器
每天洛杉矶时间 07:30 自动生成并发送报告
运行方式: python scheduler.py  （保持运行即可）
"""

import time
import logging
import sys
from datetime import datetime
from pathlib import Path

import pytz

# ─── 日志 ─────────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'scheduler.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger('scheduler')

# ─── 配置 ─────────────────────────────────────────────────────────────────────
TARGET_HOUR   = 7    # 洛杉矶时间 07
TARGET_MINUTE = 30   # :30
LA_TZ         = pytz.timezone('America/Los_Angeles')
CHECK_INTERVAL = 30  # 每 30 秒检查一次

_ran_today = None  # 记录最后一次运行的日期，避免重复触发


def should_run_now():
    """判断当前是否为洛杉矶 07:30"""
    global _ran_today
    now_la = datetime.now(LA_TZ)
    today  = now_la.date()

    if now_la.hour == TARGET_HOUR and now_la.minute == TARGET_MINUTE:
        if _ran_today != today:
            return True
    return False


def do_run():
    """执行报告生成"""
    global _ran_today
    now_la = datetime.now(LA_TZ)
    _ran_today = now_la.date()

    logger.info(f"触发每日报告 — 洛杉矶时间 {now_la.strftime('%Y-%m-%d %H:%M')}")
    try:
        # 将 daily_report 目录加入 Python 路径
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from main import run
        run()
    except Exception as e:
        logger.error(f"运行报告失败: {e}", exc_info=True)


def main():
    logger.info("=" * 60)
    logger.info(f"调度器已启动 — 每天洛杉矶时间 {TARGET_HOUR:02d}:{TARGET_MINUTE:02d} 发送报告")
    logger.info(f"检查间隔: {CHECK_INTERVAL} 秒")
    logger.info("=" * 60)

    while True:
        try:
            if should_run_now():
                do_run()
            else:
                now_la = datetime.now(LA_TZ)
                logger.debug(f"当前洛杉矶时间: {now_la.strftime('%H:%M:%S')}，等待触发…")
        except KeyboardInterrupt:
            logger.info("调度器已手动停止")
            break
        except Exception as e:
            logger.error(f"调度器异常: {e}", exc_info=True)

        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
