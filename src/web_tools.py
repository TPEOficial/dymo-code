"""
Web Tools for Dymo Code
Provides web search and URL fetching capabilities for the AI
"""

import re
import json
import ssl
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError


# ═══════════════════════════════════════════════════════════════════════════════
# HTML to Text Parser
# ═══════════════════════════════════════════════════════════════════════════════

class HTMLToTextParser(HTMLParser):
    """Convert HTML to plain text"""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_data = False
        self.skip_tags = {'script', 'style', 'noscript', 'head', 'meta', 'link'}
        self.block_tags = {'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                          'li', 'tr', 'td', 'th', 'article', 'section', 'header',
                          'footer', 'nav', 'aside', 'blockquote', 'pre'}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag.lower()
        if self.current_tag in self.skip_tags:
            self.skip_data = True
        if self.current_tag in self.block_tags:
            self.text_parts.append('\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.skip_tags:
            self.skip_data = False
        if tag in self.block_tags:
            self.text_parts.append('\n')
        self.current_tag = None

    def handle_data(self, data):
        if not self.skip_data:
            text = data.strip()
            if text:
                self.text_parts.append(text + ' ')

    def get_text(self) -> str:
        text = ''.join(self.text_parts)
        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()


def html_to_text(html: str) -> str:
    """Convert HTML to plain text"""
    parser = HTMLToTextParser()
    try:
        parser.feed(html)
        return parser.get_text()
    except Exception:
        # Fallback: simple regex removal
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# SSL Context
# ═══════════════════════════════════════════════════════════════════════════════

def create_ssl_context() -> ssl.SSLContext:
    """Create SSL context that works in compiled mode"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError: pass

    # Fallback.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# ═══════════════════════════════════════════════════════════════════════════════
# Web Fetch Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class WebFetchResult:
    """Result of fetching a URL"""
    url: str
    success: bool
    title: str = ""
    content: str = ""
    error: str = ""
    status_code: int = 0
    content_type: str = ""
    word_count: int = 0

@dataclass
class SearchResult:
    """A single search result"""
    title: str
    url: str
    snippet: str
    source: str = ""

@dataclass
class WebSearchResult:
    """Result of a web search"""
    query: str
    success: bool
    results: List[SearchResult] = None
    error: str = ""

    def __post_init__(self):
        if self.results is None: self.results = []

# ═══════════════════════════════════════════════════════════════════════════════
# URL Fetcher
# ═══════════════════════════════════════════════════════════════════════════════

class WebFetcher:
    """Fetches and parses web pages"""

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    MAX_CONTENT_LENGTH = 500000  # 500KB max
    TIMEOUT = 15  # seconds

    def __init__(self):
        self.ssl_context = create_ssl_context()

    def fetch(self, url: str, max_chars: int = 50000) -> WebFetchResult:
        """
        Fetch a URL and return its content as text.

        Args:
            url: The URL to fetch
            max_chars: Maximum characters to return

        Returns:
            WebFetchResult with the page content
        """
        result = WebFetchResult(url=url, success=False)

        try:
            # Validate URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                result.url = url

            # Create request
            request = urllib.request.Request(
                url,
                headers={
                    'User-Agent': self.USER_AGENT,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'identity',
                    'Connection': 'keep-alive'
                }
            )

            # Fetch with timeout
            with urllib.request.urlopen(
                request,
                timeout=self.TIMEOUT,
                context=self.ssl_context
            ) as response:
                result.status_code = response.status
                result.content_type = response.headers.get('Content-Type', '')

                # Check content type
                if 'text/html' not in result.content_type and 'text/plain' not in result.content_type:
                    # Try to handle JSON
                    if 'application/json' in result.content_type:
                        content = response.read(self.MAX_CONTENT_LENGTH).decode('utf-8', errors='replace')
                        result.content = content[:max_chars]
                        result.success = True
                        return result
                    else:
                        result.error = f"Unsupported content type: {result.content_type}"
                        return result

                # Read content
                raw_content = response.read(self.MAX_CONTENT_LENGTH)

                # Detect encoding
                encoding = 'utf-8'
                if 'charset=' in result.content_type:
                    match = re.search(r'charset=([^\s;]+)', result.content_type)
                    if match: encoding = match.group(1)

                html = raw_content.decode(encoding, errors='replace')

                # Extract title
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                if title_match: result.title = title_match.group(1).strip()

                # Convert to text
                text = html_to_text(html)
                result.content = text[:max_chars]
                result.word_count = len(text.split())
                result.success = True

        except urllib.error.HTTPError as e:
            result.status_code = e.code
            result.error = f"HTTP Error {e.code}: {e.reason}"

        except urllib.error.URLError as e: result.error = f"URL Error: {str(e.reason)}"

        except TimeoutError: result.error = "Request timed out"

        except Exception as e: result.error = f"Error: {str(e)}"

        return result

    def fetch_multiple(self, urls: List[str], max_chars: int = 30000) -> List[WebFetchResult]:
        """Fetch multiple URLs in parallel"""
        results = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.fetch, url, max_chars): url for url in urls}

            for future in futures:
                try:
                    result = future.result(timeout=self.TIMEOUT + 5)
                    results.append(result)
                except FuturesTimeoutError:
                    results.append(WebFetchResult(
                        url=futures[future],
                        success=False,
                        error="Request timed out"
                    ))
                except Exception as e:
                    results.append(WebFetchResult(
                        url=futures[future],
                        success=False,
                        error=str(e)
                    ))

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# Web Search (Using DuckDuckGo HTML)
# ═══════════════════════════════════════════════════════════════════════════════

class WebSearcher:
    """
    Web search using DuckDuckGo HTML interface.
    No API key required.
    """

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    TIMEOUT = 10

    def __init__(self):
        self.ssl_context = create_ssl_context()

    def search(self, query: str, num_results: int = 10) -> WebSearchResult:
        """
        Search the web using DuckDuckGo.

        Args:
            query: Search query
            num_results: Maximum number of results to return

        Returns:
            WebSearchResult with search results
        """
        result = WebSearchResult(query=query, success=False)

        try:
            # Prepare search data
            data = urllib.parse.urlencode({'q': query}).encode('utf-8')

            request = urllib.request.Request(
                self.SEARCH_URL,
                data=data,
                headers={
                    'User-Agent': self.USER_AGENT,
                    'Accept': 'text/html',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            with urllib.request.urlopen(
                request,
                timeout=self.TIMEOUT,
                context=self.ssl_context
            ) as response:
                html = response.read().decode('utf-8', errors='replace')

            # Parse results
            results = self._parse_results(html, num_results)
            result.results = results
            result.success = len(results) > 0

            if not results: result.error = "No results found"

        except Exception as e: result.error = f"Search error: {str(e)}"

        return result

    def _parse_results(self, html: str, max_results: int) -> List[SearchResult]:
        """Parse DuckDuckGo HTML results"""
        results = []

        # Find result blocks
        # DuckDuckGo HTML uses class="result" for each result
        result_pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>([^<]*(?:<[^>]+>[^<]*)*)</a>',
            re.DOTALL | re.IGNORECASE
        )

        # Alternative pattern for result extraction
        alt_pattern = re.compile(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*class="[^"]*result[^"]*"[^>]*>.*?'
            r'<span[^>]*>([^<]+)</span>',
            re.DOTALL | re.IGNORECASE
        )

        # Try main pattern first
        matches = result_pattern.findall(html)

        if not matches:
            # Try simpler pattern
            link_pattern = re.compile(
                r'<a[^>]+class="result__url"[^>]+href="([^"]+)"[^>]*>.*?</a>.*?'
                r'<a[^>]+class="result__a"[^>]*>([^<]+)</a>.*?'
                r'class="result__snippet"[^>]*>([^<]+)',
                re.DOTALL | re.IGNORECASE
            )
            matches = link_pattern.findall(html)

        if not matches:
            # Last resort: extract any links with titles
            simple_pattern = re.compile(
                r'<a[^>]+href="(https?://(?!duckduckgo)[^"]+)"[^>]*>([^<]{10,100})</a>',
                re.IGNORECASE
            )
            simple_matches = simple_pattern.findall(html)

            for url, title in simple_matches[:max_results]:
                if not any(x in url.lower() for x in ['duckduckgo', 'ad.', 'click.']):
                    results.append(SearchResult(
                        title=html_to_text(title).strip(),
                        url=url,
                        snippet="",
                        source="DuckDuckGo"
                    ))

            return results

        for match in matches[:max_results]:
            url = match[0]
            title = html_to_text(match[1]).strip()
            snippet = html_to_text(match[2]).strip() if len(match) > 2 else ""

            # Skip DuckDuckGo internal links
            if 'duckduckgo.com' in url:
                continue

            # Clean up URL (DuckDuckGo sometimes wraps URLs)
            if '//duckduckgo.com/l/?uddg=' in url:
                # Extract actual URL
                url_match = re.search(r'uddg=([^&]+)', url)
                if url_match: url = urllib.parse.unquote(url_match.group(1))

            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source="DuckDuckGo"
            ))

        return results


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Functions (For AI)
# ═══════════════════════════════════════════════════════════════════════════════

_fetcher = WebFetcher()
_searcher = WebSearcher()


def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web for information.

    Args:
        query: The search query
        num_results: Number of results to return (default 5)

    Returns:
        Formatted search results as a string
    """
    result = _searcher.search(query, num_results)

    if not result.success: return f"Search failed: {result.error}"

    output = [f"Search results for: {query}\n"]

    for i, r in enumerate(result.results, 1):
        output.append(f"{i}. {r.title}")
        output.append(f"   URL: {r.url}")
        if r.snippet: output.append(f"   {r.snippet[:200]}")
        output.append("")

    return "\n".join(output)


def fetch_url(url: str, max_chars: int = 50000) -> str:
    """
    Fetch and read the content of a URL.

    Args:
        url: The URL to fetch
        max_chars: Maximum characters to return (default 50000)

    Returns:
        The page content as text
    """
    result = _fetcher.fetch(url, max_chars)

    if not result.success: return f"Failed to fetch {url}: {result.error}"

    output = []
    if result.title: output.append(f"Title: {result.title}")
    output.append(f"URL: {result.url}")
    output.append(f"Words: {result.word_count}")
    output.append("-" * 50)
    output.append(result.content)

    return "\n".join(output)

def search_and_summarize(query: str) -> str:
    """
    Search the web and fetch top results for summarization.

    Args:
        query: The search query

    Returns:
        Combined content from top search results
    """
    # First search
    search_result = _searcher.search(query, num_results=3)

    if not search_result.success or not search_result.results: return f"No results found for: {query}"

    output = [f"Research results for: {query}\n"]

    # Fetch top results
    for r in search_result.results[:3]:
        output.append(f"## {r.title}")
        output.append(f"Source: {r.url}\n")

        fetch_result = _fetcher.fetch(r.url, max_chars=15000)
        if fetch_result.success:
            # Truncate content
            content = fetch_result.content[:10000]
            if len(fetch_result.content) > 10000: content += "\n... (content truncated)"
            output.append(content)
        else: output.append(f"Could not fetch content: {fetch_result.error}")

        output.append("\n" + "=" * 50 + "\n")

    return "\n".join(output)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Definitions (For AI Tool Calling)
# ═══════════════════════════════════════════════════════════════════════════════

WEB_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information on any topic. Use this when you need current information, facts, or to research something you don't know.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query - be specific and include relevant keywords"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (1-10, default 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and read the content of a web page. Use this when the user provides a URL or when you need to read a specific webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (must be a valid http/https URL)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_summarize",
            "description": "Search the web and fetch content from top results. Use this for research tasks when you need comprehensive information on a topic. This searches, fetches top 3 results, and combines their content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The research query - be specific about what you want to learn"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def execute_web_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Execute a web tool by name.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments

    Returns:
        Tool output as string
    """
    if tool_name == "web_search":
        query = arguments.get("query", "")
        num_results = arguments.get("num_results", 5)
        return web_search(query, num_results)

    elif tool_name == "fetch_url":
        url = arguments.get("url", "")
        return fetch_url(url)

    elif tool_name in ("search_and_summarize", "research"):
        query = arguments.get("query", "")
        return search_and_summarize(query)

    else: return f"Unknown web tool: {tool_name}"

# ═══════════════════════════════════════════════════════════════════════════════
# Global Instances
# ═══════════════════════════════════════════════════════════════════════════════

web_fetcher = _fetcher
web_searcher = _searcher