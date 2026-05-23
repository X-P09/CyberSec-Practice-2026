"""
LeetCode Daily Question Crawler
Crawls the description of LeetCode's daily question from leetcode.cn
"""

import json
import logging
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants (避免散落在代码中的魔法数字)
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 10          # seconds, applied to every HTTP call
HTTP_OK = 200
MAX_LOG_PAYLOAD = 500         # 截断打印的 API 响应长度，避免日志爆炸
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
SAFE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # 仅允许 YYYY-MM-DD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class LeetCodeCrawler:
    def __init__(self):
        self.base_url = "https://leetcode.cn"
        self.graphql_url = f"{self.base_url}/graphql"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Referer": "https://leetcode.cn/",
        })
        # SECURITY: 保持 requests 默认的 verify=True，禁止任何形式的
        # session.verify = False 或 requests.post(..., verify=False)，
        # 否则会丧失 TLS 证书校验，存在中间人攻击 (MITM) 风险。
        assert self.session.verify is True, "TLS 证书校验必须开启"

    def get_daily_question(self):
        """Get today's daily question info"""
        query = """
        query questionOfToday {
            todayRecord {
                date
                userStatus
                question {
                    questionId
                    frontendQuestionId: questionFrontendId
                    difficulty
                    title
                    titleSlug
                    paidOnly: isPaidOnly
                    acRate
                    status
                    topicTags {
                        name
                        nameTranslated: translatedName
                        id
                    }
                }
            }
        }
        """

        try:
            response = self.session.post(
                self.graphql_url,
                json={"query": query},
                timeout=REQUEST_TIMEOUT,
            )
            logger.info("Daily question API response status: %s", response.status_code)

            if response.status_code == HTTP_OK:
                data = response.json()
                if data.get("data") and data["data"].get("todayRecord"):
                    records = data["data"]["todayRecord"]
                    if records:
                        return records[0]
                else:
                    logger.warning(
                        "API response: %s",
                        json.dumps(data, indent=2, ensure_ascii=False)[:MAX_LOG_PAYLOAD],
                    )
            else:
                logger.error("API error: %s", response.text[:MAX_LOG_PAYLOAD])
        except (requests.RequestException, ValueError) as e:
            logger.exception("Request error: %s", e)
        return None

    def get_question_detail(self, title_slug):
        """Get question detail by title slug"""
        query = """
        query questionData($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                questionFrontendId
                title
                titleSlug
                translatedTitle
                translatedContent
                content
                difficulty
                topicTags {
                    name
                    translatedName
                }
                hints
                sampleTestCase
            }
        }
        """

        try:
            response = self.session.post(
                self.graphql_url,
                json={
                    "query": query,
                    "variables": {"titleSlug": title_slug},
                },
                timeout=REQUEST_TIMEOUT,
            )
            logger.info("Question detail API response status: %s", response.status_code)

            if response.status_code == HTTP_OK:
                data = response.json()
                if data.get("data") and data["data"].get("question"):
                    return data["data"]["question"]
                else:
                    logger.warning(
                        "API response: %s",
                        json.dumps(data, indent=2, ensure_ascii=False)[:MAX_LOG_PAYLOAD],
                    )
            else:
                logger.error("API error: %s", response.text[:MAX_LOG_PAYLOAD])
        except (requests.RequestException, ValueError) as e:
            logger.exception("Request error: %s", e)
        return None

    def clean_html(self, html_content):
        """Clean HTML content to readable text"""
        if not html_content:
            return ""

        # 特殊处理 <pre> 代码块：把其中的尖括号临时替换为方括号，
        # 防止后续 `<[^>]+>` 的全局清洗把代码示例里的 <、> 当成 HTML 标签误删。
        # 这是有意为之的"反直觉"处理，重构时请保留。
        text = re.sub(
            r'<pre[^>]*>.*?</pre>',
            lambda m: m.group(0).replace('<', '[').replace('>', ']'),
            html_content,
            flags=re.DOTALL,
        )
        text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text)
        text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text)
        text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text)
        text = re.sub(r'<li[^>]*>', '• ', text)
        text = re.sub(r'</li>', '\n', text)
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = unescape(text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def crawl_daily_question(self):
        """Main method to crawl daily question"""
        logger.info("=" * 60)
        logger.info("LeetCode Daily Question Crawler")
        logger.info("Date: %s", datetime.now().strftime('%Y-%m-%d'))
        logger.info("=" * 60)

        # Get daily question info
        logger.info("Fetching daily question...")
        daily_info = self.get_daily_question()

        if not daily_info:
            logger.error("Failed to get daily question info")
            return None

        question_info = daily_info.get("question", {})
        title_slug = question_info.get("titleSlug")

        if not title_slug:
            logger.error("Failed to get question slug")
            return None

        # Get question detail
        logger.info("Fetching question detail for: %s", title_slug)
        detail = self.get_question_detail(title_slug)

        if not detail:
            logger.error("Failed to get question detail")
            return None

        # Build result
        result = {
            "date": daily_info.get("date"),
            "question_id": detail.get("questionFrontendId"),
            "title": detail.get("title"),
            "title_cn": detail.get("translatedTitle"),
            "difficulty": detail.get("difficulty"),
            "url": f"{self.base_url}/problems/{title_slug}/description/",
            "tags": [tag.get("translatedName") or tag.get("name") for tag in detail.get("topicTags", [])],
            "content_cn": self.clean_html(detail.get("translatedContent")),
            "content_en": self.clean_html(detail.get("content")),
            "hints": detail.get("hints", []),
            "sample_test_case": detail.get("sampleTestCase"),
        }

        return result

    def print_result(self, result):
        """Print crawl result in readable format"""
        if not result:
            return

        print("\n" + "=" * 60)
        print(f"Question #{result['question_id']}: {result['title_cn']}")
        print(f"English Title: {result['title']}")
        print(f"Difficulty: {result['difficulty']}")
        print(f"Date: {result['date']}")
        print(f"URL: {result['url']}")
        print(f"Tags: {', '.join(result['tags'])}")
        print("=" * 60)

        print("\n[Description (Chinese)]")
        print("-" * 40)
        print(result['content_cn'])

        if result.get('hints'):
            print("\n[Hints]")
            print("-" * 40)
            for i, hint in enumerate(result['hints'], 1):
                print(f"{i}. {self.clean_html(hint)}")

        print("\n" + "=" * 60)


def _safe_output_path(date_str: str) -> Path:
    """根据 date 字段生成安全的输出路径。

    SECURITY: date_str 来自远端 API，不能直接拼接到文件名里，
    否则攻击者可通过返回 "../../evil" 之类的值实现路径穿越，
    把文件写到仓库外的任意位置。这里做三层防护：
      1) 用正则强校验 date 必须是 YYYY-MM-DD；
      2) 用 Path.name 兜底剥离任何路径分隔符；
      3) 强制写入到固定的 OUTPUT_DIR 下。
    """
    if not date_str or not SAFE_DATE_RE.match(date_str):
        raise ValueError(f"unsafe date value from API: {date_str!r}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = Path(f"daily_question_{date_str}.json").name  # 二次防御
    target = (OUTPUT_DIR / file_name).resolve()

    # 最终再校验解析后的路径仍在 OUTPUT_DIR 之内
    if OUTPUT_DIR.resolve() not in target.parents:
        raise ValueError(f"resolved path escapes OUTPUT_DIR: {target}")
    return target


def main():
    crawler = LeetCodeCrawler()
    result = crawler.crawl_daily_question()

    if not result:
        logger.error("Failed to crawl daily question")
        return

    crawler.print_result(result)

    # Print JSON result to terminal
    print("\n" + "=" * 60)
    print("[JSON Result]")
    print("=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Save to file (path-traversal hardened)
    try:
        output_file = _safe_output_path(result.get("date", ""))
    except ValueError as e:
        logger.error("Refuse to write output: %s", e)
        return

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 60)
    print(f"Result saved to: {output_file}")


if __name__ == "__main__":
    main()
