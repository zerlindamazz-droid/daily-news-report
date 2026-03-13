"""
翻译模块
使用 Google Translate (deep-translator) 为每篇文章生成中英文双语摘要
- 中文来源 (PA News) → summary_zh 保留原文，summary_en 翻译为英文
- 英文来源 (Reuters/BBC 等) → summary_en 保留原文，summary_zh 翻译为中文
"""

import time
import logging
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

MAX_CHARS = 300   # 翻译文本上限
DELAY     = 0.4   # 每次翻译间隔（秒），避免触发频率限制


def _translate(text, target):
    """翻译单段文字，失败时返回原文"""
    if not text or not text.strip():
        return ''
    try:
        chunk = text[:MAX_CHARS]
        result = GoogleTranslator(source='auto', target=target).translate(chunk)
        return result or text
    except Exception as e:
        logger.debug(f"翻译失败 (target={target}): {e}")
        return text


def enrich_articles_with_bilingual_summary(all_news):
    """
    为 all_news 中所有文章添加 summary_zh 和 summary_en 字段。
    直接修改传入的字典，无返回值。

    PA News 文章 (lang='zh') → 翻译摘要为英文
    其他文章 (lang='en')     → 翻译摘要为中文
    """
    total = sum(len(v) for v in all_news.values())
    done  = 0

    for category, articles in all_news.items():
        for article in articles:
            lang    = article.get('lang', 'en')
            summary = article.get('summary', '') or ''

            if lang == 'zh':
                # PA News：中文原文 + 翻译成英文
                article['summary_zh'] = summary
                if summary:
                    article['summary_en'] = _translate(summary, target='en')
                    time.sleep(DELAY)
                else:
                    article['summary_en'] = ''
            else:
                # 英文来源：英文原文 + 翻译成中文
                article['summary_en'] = summary
                if summary:
                    article['summary_zh'] = _translate(summary, target='zh-CN')
                    time.sleep(DELAY)
                else:
                    article['summary_zh'] = ''

            done += 1
            logger.debug(f"  [{done}/{total}] 翻译完成: {article['title'][:30]}")

    logger.info(f"双语摘要生成完毕，共 {total} 篇文章")
