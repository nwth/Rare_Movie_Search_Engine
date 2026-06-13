"""Cloud drive extraction code (提取码) auto-extractor.

When search results contain cloud drive links (Baidu Pan, Aliyun Drive, Quark),
this module tries to automatically find the extraction code by:
1. Parsing the same page where the link was found
2. Searching the web for the share link + 提取码
3. Using known patterns/common codes
"""

import asyncio
import logging
import random
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from core.crawlers.base import USER_AGENTS

logger = logging.getLogger(__name__)

# ===== Regex patterns for 提取码 =====

# Standard patterns: 提取码：xxxx, 密码：xxxx, 提取码:xxxx
EXTRACTION_CODE_PATTERNS = [
    re.compile(r"提取码[：:\s]*([a-zA-Z0-9]{4,6})"),
    re.compile(r"密码[：:\s]*([a-zA-Z0-9]{4,6})"),
    re.compile(r"提取码[：:\s]*[（(]?([a-zA-Z0-9]{4,6})[）)]?"),
    re.compile(r"密码[：:\s]*[（(]?([a-zA-Z0-9]{4,6})[）)]?"),
    re.compile(r"访问码[：:\s]*([a-zA-Z0-9]{4,6})"),
    re.compile(r"pwd[=：:\s]*([a-zA-Z0-9]{4,6})"),
    re.compile(r"code[=：:\s]*([a-zA-Z0-9]{4,6})"),
    re.compile(r"提取密码[：:\s]*([a-zA-Z0-9]{4,6})"),
]

# Common default codes
COMMON_CODES = [
    "1234", "8888", "6666", "1111", "0000",
    "abcd", "123456", "888888", "666666",
]

# Baidu Pan specific: look for /s/ link followed by code
BAIDU_CODE_PATTERN = re.compile(
    r"pan\.baidu\.com/s/[^\s'\"]+[\s\S]{0,200}?"
    r"(?:提取码|密码|pwd)[：:\s]*([a-zA-Z0-9]{4,6})",
    re.IGNORECASE,
)

# Quark specific patterns
QUARK_CODE_PATTERN = re.compile(
    r"pan\.quark\.cn/s/[^\s'\"]+[\s\S]{0,200}?"
    r"(?:提取码|密码|pwd)[：:\s]*([a-zA-Z0-9]{4,6})",
    re.IGNORECASE,
)


class ExtractionCodeResult:
    """Result of extraction code lookup."""

    def __init__(
        self,
        code: Optional[str] = None,
        source: str = "",
        confidence: float = 0.0,
    ):
        self.code = code
        self.source = source
        self.confidence = confidence

    def __bool__(self):
        return self.code is not None

    def __repr__(self) -> str:
        return f"ExtractionCode(code={self.code}, source={self.source}, confidence={self.confidence})"


class CloudDriveExtractor:
    """Auto-extract 提取码 for cloud drive share links."""

    @staticmethod
    def detect_cloud_type(url: str) -> str:
        """Detect which cloud drive service a URL belongs to."""
        domain = urlparse(url).netloc.lower()
        if "baidu" in domain:
            return "baidu"
        if "aliyundrive" in domain or "aliyun" in domain:
            return "aliyun"
        if "quark" in domain:
            return "quark"
        if "123pan" in domain:
            return "123pan"
        if "115" in domain:
            return "115"
        return "unknown"

    @staticmethod
    def extract_code_from_text(text: str) -> Optional[ExtractionCodeResult]:
        """Try to extract a 提取码 from arbitrary text.

        Tries multiple regex patterns and returns the best match.
        """
        for i, pattern in enumerate(EXTRACTION_CODE_PATTERNS):
            match = pattern.search(text)
            if match:
                code = match.group(1).strip()
                # Validate: 4-6 alphanumeric chars
                if re.match(r"^[a-zA-Z0-9]{4,6}$", code):
                    confidence = 0.9 - (i * 0.05)  # Earlier patterns = higher confidence
                    return ExtractionCodeResult(
                        code=code,
                        source=f"pattern_{i}",
                        confidence=max(0.5, confidence),
                    )
        return None

    @staticmethod
    def extract_code_from_html(html: str, cloud_url: str) -> Optional[ExtractionCodeResult]:
        """Search through HTML content for extraction code near the cloud link."""
        cloud_type = CloudDriveExtractor.detect_cloud_type(cloud_url)
        soup = BeautifulSoup(html, "lxml")

        # Strategy 1: Look for code near the cloud link in the HTML
        text_content = soup.get_text(separator="\n", strip=True)

        # Find lines containing the cloud URL and read surrounding context
        lines = text_content.split("\n")
        relevant_text = ""
        for i, line in enumerate(lines):
            if cloud_url[:40] in line or cloud_url.split("/s/")[-1][:20] in line:
                # Capture 5 lines before and after
                start = max(0, i - 5)
                end = min(len(lines), i + 6)
                relevant_text = "\n".join(lines[start:end])
                break

        if relevant_text:
            result = CloudDriveExtractor.extract_code_from_text(relevant_text)
            if result:
                result.source = "html_context"
                return result

        # Strategy 2: Search entire page text
        result = CloudDriveExtractor.extract_code_from_text(text_content)
        if result:
            result.source = "html_full"
            return result

        # Strategy 3: Check for common codes
        # Some sharers use predictable codes
        for code in COMMON_CODES:
            if code in text_content:
                return ExtractionCodeResult(
                    code=code,
                    source="common_code_match",
                    confidence=0.3,
                )

        return None

    @staticmethod
    async def search_code_for_url(cloud_url: str, timeout: float = 8.0) -> Optional[ExtractionCodeResult]:
        """Search the web for an extraction code for a specific share URL.

        Uses Google/Bing search to find pages that mention both the
        share URL and its extraction code.
        """
        search_queries = [
            f'"{cloud_url[:60]}" 提取码',
            f'"{cloud_url.split("/s/")[-1][:20]}" 提取码',
        ]

        headers = {"User-Agent": random.choice(USER_AGENTS)}

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            for query in search_queries:
                try:
                    resp = await client.get(
                        "https://www.google.com/search",
                        params={"q": query, "num": "5"},
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        result = CloudDriveExtractor.extract_code_from_html(
                            resp.text, cloud_url
                        )
                        if result:
                            result.source = "web_search"
                            return result
                except Exception:
                    continue

        return None

    @staticmethod
    def encode_extraction_url(cloud_url: str, code: str) -> str:
        """Create a URL with the extraction code embedded.

        Some cloud drives support passing the code in the URL.
        """
        cloud_type = CloudDriveExtractor.detect_cloud_type(cloud_url)

        if cloud_type == "baidu":
            # Baidu Pan: ?pwd=CODE
            separator = "&" if "?" in cloud_url else "?"
            return f"{cloud_url}{separator}pwd={code}"

        return cloud_url  # Most don't support URL-encoded codes


class CloudExtractionPipeline:
    """Full pipeline for extracting cloud drive codes."""

    @staticmethod
    async def process(
        cloud_url: str,
        context_html: Optional[str] = None,
    ) -> ExtractionCodeResult:
        """Run the full extraction pipeline.

        Steps:
        1. Parse context HTML (from the page where link was found)
        2. Search web for code (Google dork)
        3. Return best result or empty
        """
        result = ExtractionCodeResult()

        # Step 1: Extract from context HTML
        if context_html:
            result = CloudDriveExtractor.extract_code_from_html(context_html, cloud_url)
            if result:
                logger.info(f"Found code {result.code} from context HTML")
                return result

        # Step 2: Search web
        result = await CloudDriveExtractor.search_code_for_url(cloud_url)
        if result:
            logger.info(f"Found code {result.code} from web search")
            return result

        logger.debug(f"No extraction code found for {cloud_url[:60]}...")
        return ExtractionCodeResult()

    @staticmethod
    def enrich_search_result(
        result_dict: dict,
        code_result: ExtractionCodeResult,
    ) -> dict:
        """Add extraction code info to a search result."""
        if code_result:
            result_dict["extraction_code"] = code_result.code
            result_dict["extraction_code_confidence"] = round(code_result.confidence, 2)
            result_dict["extraction_code_source"] = code_result.source

            # Add code-encoded URL
            result_dict["url_with_code"] = CloudDriveExtractor.encode_extraction_url(
                result_dict.get("url", ""), code_result.code
            )

        return result_dict
