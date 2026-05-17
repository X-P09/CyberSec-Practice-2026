"""
LeetCode Daily Question Crawler
Crawls the description of LeetCode's daily question from leetcode.cn
"""

import requests
import json
from datetime import datetime
import re
from html import unescape


class LeetCodeCrawler:
    # 类常量：避免魔法数字
    REQUEST_TIMEOUT = 10          # HTTP请求超时时间（秒）
    ERROR_PREVIEW_LEN = 500       # 错误响应预览长度
    SEPARATOR_LEN = 60            # 打印分隔线长度

    def __init__(self):
        self.base_url = "https://leetcode.cn"
        self.graphql_url = f"{self.base_url}/graphql"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Referer": "https://leetcode.cn/",
        })

    def get_daily_question(self):
        """获取今日每日一题的基本信息"""
        # GraphQL查询：获取今日题目记录
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
                timeout=self.REQUEST_TIMEOUT
            )
            print(f"Daily question API response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get("data") and data["data"].get("todayRecord"):
                    daily_records = data["data"]["todayRecord"]
                    if daily_records:
                        return daily_records[0]   # 取第一条记录
                else:
                    print(f"API response: {json.dumps(data, indent=2, ensure_ascii=False)[:self.ERROR_PREVIEW_LEN]}")
            else:
                print(f"API error: {response.text[:self.ERROR_PREVIEW_LEN]}")
        except Exception as e:
            print(f"Request error: {e}")
        return None

    def get_question_detail(self, title_slug):
        """根据题目slug获取题目详细信息（描述、标签、提示等）"""
        # GraphQL查询：通过题目slug获取详情
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
                    "variables": {"titleSlug": title_slug}
                },
                timeout=self.REQUEST_TIMEOUT
            )
            print(f"Question detail API response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get("data") and data["data"].get("question"):
                    return data["data"]["question"]
                else:
                    print(f"API response: {json.dumps(data, indent=2, ensure_ascii=False)[:self.ERROR_PREVIEW_LEN]}")
            else:
                print(f"API error: {response.text[:self.ERROR_PREVIEW_LEN]}")
        except Exception as e:
            print(f"Request error: {e}")
        return None

    def clean_html(self, html_content):
        """
        将HTML内容转换为可读的纯文本格式
        处理步骤：
        1. 保护<pre>代码块内容（避免内部标签被误删）
        2. 将<code>转为反引号形式
        3. 将<strong>/<em>转为Markdown标记
        4. 处理列表项<li>为项目符号
        5. 将块级标签转为换行符
        6. 移除剩余所有HTML标签
        7. 解码HTML实体并清理多余空行
        """
        if not html_content:
            return ""

        # 保护<pre>中的内容，临时替换尖括号以防被后续正则破坏
        text = re.sub(r'<pre[^>]*>.*?</pre>', 
                      lambda m: m.group(0).replace('<', '[').replace('>', ']'), 
                      html_content, flags=re.DOTALL)
        # 行内代码：<code>包裹的内容用反引号包围
        text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text)
        # 粗体：<strong>转换为**文本**
        text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text)
        # 斜体：<em>转换为*文本*
        text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text)
        # 列表项：<li>替换为项目符号•，并在末尾加换行
        text = re.sub(r'<li[^>]*>', '• ', text)
        text = re.sub(r'</li>', '\n', text)
        # 段落和换行：<p>和<br>转换为换行符
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        text = re.sub(r'<br\s*/?>', '\n', text)
        # 删除所有剩余的HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 解码HTML实体（如 &nbsp; -> 空格）
        text = unescape(text)
        # 合并连续三个以上的换行为两个换行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def crawl_daily_question(self):
        """主流程：获取每日一题并组装结果字典"""
        print("=" * self.SEPARATOR_LEN)
        print(f"LeetCode Daily Question Crawler")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        print("=" * self.SEPARATOR_LEN)

        # 第一步：获取今日题目概要
        print("\nFetching daily question...")
        daily_info = self.get_daily_question()

        if not daily_info:
            print("Failed to get daily question info")
            return None

        question_info = daily_info.get("question", {})
        title_slug = question_info.get("titleSlug")

        if not title_slug:
            print("Failed to get question slug")
            return None

        # 第二步：获取题目详细内容
        print(f"Fetching question detail for: {title_slug}")
        detail = self.get_question_detail(title_slug)

        if not detail:
            print("Failed to get question detail")
            return None

        # 第三步：组装结果
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
        """将爬取结果以可读格式打印到控制台"""
        if not result:
            return

        print("\n" + "=" * self.SEPARATOR_LEN)
        print(f"Question #{result['question_id']}: {result['title_cn']}")
        print(f"English Title: {result['title']}")
        print(f"Difficulty: {result['difficulty']}")
        print(f"Date: {result['date']}")
        print(f"URL: {result['url']}")
        print(f"Tags: {', '.join(result['tags'])}")
        print("=" * self.SEPARATOR_LEN)

        print("\n[Description (Chinese)]")
        print("-" * 40)
        print(result['content_cn'])

        if result.get('hints'):
            print("\n[Hints]")
            print("-" * 40)
            for i, hint in enumerate(result['hints'], 1):
                print(f"{i}. {self.clean_html(hint)}")

        print("\n" + "=" * self.SEPARATOR_LEN)


def main():
    crawler = LeetCodeCrawler()
    result = crawler.crawl_daily_question()

    if result:
        crawler.print_result(result)

        # 输出JSON格式结果
        print("\n" + "=" * LeetCodeCrawler.SEPARATOR_LEN)
        print("[JSON Result]")
        print("=" * LeetCodeCrawler.SEPARATOR_LEN)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 保存到文件
        output_file = f"daily_question_{result['date']}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("\n" + "=" * LeetCodeCrawler.SEPARATOR_LEN)
        print(f"Result saved to: {output_file}")
    else:
        print("Failed to crawl daily question")


if __name__ == "__main__":
    main()