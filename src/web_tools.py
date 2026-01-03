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
import src.utils.bypasses.cloudscraper as cloudscraper
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Dymo API for URL verification
try:
    from dymoapi import DymoAPI
    DYMO_AVAILABLE = True
except ImportError:
    DYMO_AVAILABLE = False


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
        if self.current_tag in self.skip_tags: self.skip_data = True
        if self.current_tag in self.block_tags: self.text_parts.append('\n')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.skip_tags: self.skip_data = False
        if tag in self.block_tags: self.text_parts.append('\n')
        self.current_tag = None

    def handle_data(self, data):
        if not self.skip_data:
            text = data.strip()
            if text: self.text_parts.append(text + ' ')

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
# URL Verifier (Dymo API)
# ═══════════════════════════════════════════════════════════════════════════════

class URLVerifier:
    """Verifies URLs using Dymo API before fetching"""

    def __init__(self):
        self._dymo = None
        self._enabled = True  # Enabled by default if API key is available
        self._rejected_domains = set()  # Cache of domains user rejected
        self._accepted_domains = set()  # Cache of domains user accepted (proceed at risk)
        self._load_settings()
        self._load_domain_decisions()

    def _load_settings(self):
        """Load settings from storage"""
        try:
            from .storage import user_config
            self._enabled = user_config.get("url_verification_enabled", True)
        except Exception:
            pass

    def _save_settings(self):
        """Save settings to storage"""
        try:
            from .storage import user_config
            user_config.set("url_verification_enabled", self._enabled)
        except Exception:
            pass

    def _load_domain_decisions(self):
        """Load domain decisions from storage"""
        try:
            from .storage import user_config
            rejected = user_config.get("rejected_domains", [])
            accepted = user_config.get("accepted_domains", [])
            self._rejected_domains = set(rejected)
            self._accepted_domains = set(accepted)
        except Exception:
            pass

    def _save_domain_decisions(self):
        """Save domain decisions to storage"""
        try:
            from .storage import user_config
            user_config.set("rejected_domains", list(self._rejected_domains))
            user_config.set("accepted_domains", list(self._accepted_domains))
        except Exception:
            pass

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing www. prefix and converting to lowercase"""
        domain = domain.lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _get_client(self):
        """Get Dymo API client (lazy initialization)"""
        if self._dymo is None and DYMO_AVAILABLE:
            try:
                from .api_key_manager import api_key_manager
                api_key = api_key_manager.get_key("dymo")
                if api_key:
                    self._dymo = DymoAPI({"api_key": api_key})
            except Exception:
                pass
        return self._dymo

    def set_enabled(self, enabled: bool):
        """Enable or disable URL verification"""
        self._enabled = enabled
        self._save_settings()

    def is_enabled(self) -> bool:
        """Check if verification is enabled"""
        return self._enabled

    def is_available(self) -> bool:
        """Check if Dymo API verification is available (has API key)"""
        try:
            from .api_key_manager import api_key_manager
            return api_key_manager.get_key("dymo") is not None
        except Exception:
            return False

    def is_domain_rejected(self, domain: str) -> bool:
        """Check if user already rejected this domain"""
        return self._normalize_domain(domain) in self._rejected_domains

    def add_rejected_domain(self, domain: str):
        """Add domain to rejected list and persist"""
        self._rejected_domains.add(self._normalize_domain(domain))
        self._save_domain_decisions()

    def is_domain_accepted(self, domain: str) -> bool:
        """Check if user already accepted this domain (proceed at risk)"""
        return self._normalize_domain(domain) in self._accepted_domains

    def add_accepted_domain(self, domain: str):
        """Add domain to accepted list and persist"""
        self._accepted_domains.add(self._normalize_domain(domain))
        self._save_domain_decisions()

    def remove_domain_decision(self, domain: str) -> bool:
        """Remove domain from both lists (reset decision). Returns True if found."""
        normalized = self._normalize_domain(domain)
        found = False
        if normalized in self._rejected_domains:
            self._rejected_domains.remove(normalized)
            found = True
        if normalized in self._accepted_domains:
            self._accepted_domains.remove(normalized)
            found = True
        if found:
            self._save_domain_decisions()
        return found

    def allow_domain(self, domain: str):
        """Explicitly allow a domain (move from rejected to accepted)"""
        normalized = self._normalize_domain(domain)
        if normalized in self._rejected_domains:
            self._rejected_domains.remove(normalized)
        self._accepted_domains.add(normalized)
        self._save_domain_decisions()

    def block_domain(self, domain: str):
        """Explicitly block a domain (move from accepted to rejected)"""
        normalized = self._normalize_domain(domain)
        if normalized in self._accepted_domains:
            self._accepted_domains.remove(normalized)
        self._rejected_domains.add(normalized)
        self._save_domain_decisions()

    def get_rejected_domains(self) -> list:
        """Get list of rejected domains"""
        return sorted(self._rejected_domains)

    def get_accepted_domains(self) -> list:
        """Get list of accepted domains"""
        return sorted(self._accepted_domains)

    def verify_url(self, url: str) -> dict:
        """
        Verify a URL using Dymo API.
        Returns dict with 'safe' (bool), 'reason' (str), 'details' (dict)
        """
        if not self._enabled:
            return {"safe": True, "reason": "verification_disabled", "details": {}}

        try:
            from .api_key_manager import api_key_manager
            import requests

            api_key = api_key_manager.get_key("dymo")
            if not api_key:
                return {"safe": True, "reason": "no_api_key", "details": {}}

            # Extract domain from URL
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc

            # Use direct API call (more reliable than SDK)
            response = requests.post(
                'https://api.tpeoficial.com/v1/private/secure/verify',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={'url': url, 'domain': domain},
                timeout=10
            )

            if response.status_code != 200:
                return {"safe": True, "reason": f"api_error_{response.status_code}", "details": {}}

            result = response.json()

            # Analyze response
            url_data = result.get("url", {})
            domain_data = result.get("domain", {})

            is_safe = True
            reason = "verified"

            # Check for fraud
            if url_data.get("fraud") or domain_data.get("fraud"):
                is_safe = False
                reason = "fraud_detected"
            elif not url_data.get("valid"):
                is_safe = False
                reason = "invalid_url"

            return {
                "safe": is_safe,
                "reason": reason,
                "details": result
            }
        except Exception as e:
            # Fail-open: allow fetch on verification error
            return {"safe": True, "reason": f"verification_error: {e}", "details": {}}


_url_verifier = URLVerifier()


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
    MAX_CONTENT_LENGTH = 500000 # 500KB max.
    TIMEOUT = 15 # seconds.

    def __init__(self):
        self.ssl_context = create_ssl_context()
        self._scraper = None

    def _get_scraper(self):
        if self._scraper is None: self._scraper = cloudscraper.create_scraper()
        return self._scraper

    def _confirm_fraudulent_url(self, url: str, verification: dict, domain: str = None) -> bool:
        """
        Show visual warning for fraudulent URL and ask user for confirmation.
        Returns True if user wants to continue, False otherwise.
        """
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            from rich.box import HEAVY

            console = Console()

            # Pause spinner and clear line to avoid output conflicts
            try:
                from .terminal_ui import pause_spinner
                pause_spinner()
            except Exception:
                pass
            import sys
            sys.stdout.write("\r\033[K")  # Clear current line
            sys.stdout.flush()

            details = verification.get("details", {})
            url_data = details.get("url", {})
            domain_data = details.get("domain", {})

            # Extract domain if not provided
            if not domain:
                parsed = urllib.parse.urlparse(url)
                domain = parsed.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]

            # Build warning message
            warning = Text()
            warning.append("🚨 FRAUDULENT SITE DETECTED 🚨\n\n", style="bold red")
            warning.append(f"URL: ", style="dim")
            warning.append(f"{url}\n", style="bold white")
            warning.append(f"Domain: ", style="dim")
            warning.append(f"{domain}\n\n", style="bold white")

            warning.append("Security Analysis:\n", style="bold yellow")
            warning.append(f"  • URL Valid: ", style="dim")
            warning.append(f"{'Yes' if url_data.get('valid') else 'No'}\n", style="green" if url_data.get('valid') else "red")
            warning.append(f"  • URL Fraud: ", style="dim")
            warning.append(f"{'YES' if url_data.get('fraud') else 'No'}\n", style="bold red" if url_data.get('fraud') else "green")
            warning.append(f"  • Domain Fraud: ", style="dim")
            warning.append(f"{'YES' if domain_data.get('fraud') else 'No'}\n", style="bold red" if domain_data.get('fraud') else "green")

            warning.append("\nThis site may steal your data or infect your device.\n", style="bold yellow")
            warning.append("Recommendation: DO NOT CONTINUE\n\n", style="bold red")
            warning.append(f"To change this decision later, use:\n", style="dim")
            warning.append(f"  /domain allow {domain}\n", style="cyan")
            warning.append(f"  /domain block {domain}\n", style="cyan")

            console.print()
            console.print(Panel(
                warning,
                title="[bold red]SECURITY WARNING[/]",
                border_style="red",
                box=HEAVY,
                padding=(1, 2)
            ))

            # Ask for confirmation
            console.print()
            console.print("[bold yellow]Do you want to continue anyway? (not recommended)[/]")
            console.print("[dim]Type 'yes' to continue or press Enter to cancel:[/] ", end="")

            try:
                response = input().strip().lower()
                # Resume spinner
                try:
                    from .terminal_ui import resume_spinner
                    resume_spinner()
                except Exception:
                    pass

                if response in ('yes', 'y'):
                    console.print("[yellow]Proceeding at your own risk...[/]\n")
                    return True
                else:
                    console.print("[green]URL access cancelled for your safety.[/]\n")
                    return False
            except (KeyboardInterrupt, EOFError):
                console.print("\n[green]URL access cancelled.[/]\n")
                return False

        except Exception:
            # If Rich is not available or any error, default to blocking
            return False

    def _fetch_with_cloudscraper(self, url: str, max_chars: int) -> WebFetchResult:
        result = WebFetchResult(url=url, success=False)

        scraper = self._get_scraper()
        if scraper is None:
            result.error = "Cloudscraper not available"
            return result

        try:
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': url
            }

            response = scraper.get(url, headers=headers, timeout=self.TIMEOUT)
            result.status_code = response.status_code
            result.content_type = response.headers.get('Content-Type', '')

            if response.status_code != 200:
                result.error = f"HTTP Error {response.status_code}"
                return result

            # Check content type
            if 'text/html' not in result.content_type and 'text/plain' not in result.content_type:
                if 'application/json' in result.content_type:
                    result.content = response.text[:max_chars]
                    result.success = True
                    return result
                else:
                    result.error = f"Unsupported content type: {result.content_type}"
                    return result

            html = response.text

            # Extract title.
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            if title_match: result.title = title_match.group(1).strip()

            # Convert to text.
            text = html_to_text(html)
            result.content = text[:max_chars]
            result.word_count = len(text.split())
            result.success = True

        except Exception as e: result.error = f"Cloudscraper error: {str(e)}"

        return result

    def fetch(self, url: str, max_chars: int = 50000, verify_url: bool = True) -> WebFetchResult:
        """
        Fetch a URL and return its content as text.

        Args:
            url: The URL to fetch
            max_chars: Maximum characters to return
            verify_url: Whether to verify URL with Dymo API (default True if available)

        Returns:
            WebFetchResult with the page content
        """
        result = WebFetchResult(url=url, success=False)

        try:
            # Validate URL.
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                result.url = url

            # Verify URL with Dymo API if enabled
            if verify_url and _url_verifier.is_available():
                # Extract and normalize domain for cache check
                parsed = urllib.parse.urlparse(url)
                domain = _url_verifier._normalize_domain(parsed.netloc)

                # Check if user already rejected this domain
                if _url_verifier.is_domain_rejected(domain):
                    result.error = (
                        f"ACCESS DENIED: Domain '{domain}' was previously blocked. "
                        f"Use '/domain allow {domain}' to unblock. DO NOT retry."
                    )
                    return result

                # Check if user already accepted this domain (skip verification)
                if _url_verifier.is_domain_accepted(domain):
                    pass  # User already accepted risk, proceed without asking

                else:
                    verification = _url_verifier.verify_url(url)
                    if not verification["safe"]:
                        # Show visual warning and ask user for confirmation
                        if self._confirm_fraudulent_url(url, verification, domain):
                            # User accepted, cache the decision
                            _url_verifier.add_accepted_domain(domain)
                        else:
                            # User rejected, cache the decision
                            _url_verifier.add_rejected_domain(domain)
                            result.error = (
                                f"ACCESS DENIED: Fraudulent site '{domain}' blocked. "
                                f"Use '/domain allow {domain}' to unblock if needed. DO NOT retry."
                            )
                            return result

            # Create request.
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

                # Check content type.
                if 'text/html' not in result.content_type and 'text/plain' not in result.content_type:
                    # Try to handle JSON.
                    if 'application/json' in result.content_type:
                        content = response.read(self.MAX_CONTENT_LENGTH).decode('utf-8', errors='replace')
                        result.content = content[:max_chars]
                        result.success = True
                        return result
                    else:
                        result.error = f"Unsupported content type: {result.content_type}"
                        return result

                # Read content.
                raw_content = response.read(self.MAX_CONTENT_LENGTH)

                # Detect encoding.
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
            if e.code == 403: return self._fetch_with_cloudscraper(url, max_chars)
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
        self._scraper = None

    def _get_scraper(self):
        if self._scraper is None: self._scraper = cloudscraper.create_scraper()
        return self._scraper

    def _search_with_cloudscraper(self, query: str, num_results: int) -> WebSearchResult:
        result = WebSearchResult(query=query, success=False)

        scraper = self._get_scraper()
        if scraper is None:
            result.error = "Cloudscraper not available"
            return result

        try:
            headers = {
                'Accept': 'text/html',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': self.SEARCH_URL
            }

            response = scraper.post(
                self.SEARCH_URL,
                data={'q': query},
                headers=headers,
                timeout=self.TIMEOUT
            )

            if response.status_code != 200:
                result.error = f"HTTP Error {response.status_code}"
                return result

            html = response.text
            results = self._parse_results(html, num_results)
            result.results = results
            result.success = len(results) > 0

            if not results: result.error = "No results found"

        except Exception as e: result.error = f"Cloudscraper search error: {str(e)}"

        return result

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
            # Prepare search data.
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

            # Parse results.
            results = self._parse_results(html, num_results)
            result.results = results
            result.success = len(results) > 0

            if not results: result.error = "No results found"

        except urllib.error.HTTPError as e:
            if e.code == 403: return self._search_with_cloudscraper(query, num_results)
            result.error = f"Search error: HTTP {e.code}"

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


def fetch_url(url: str, max_chars: int = 50000, verify: bool = True) -> str:
    """
    Fetch and read the content of a URL.

    Args:
        url: The URL to fetch
        max_chars: Maximum characters to return (default 50000)
        verify: Verify URL safety with Dymo API (default True if API key configured)

    Returns:
        The page content as text
    """
    result = _fetcher.fetch(url, max_chars, verify_url=verify)

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
# URL Verification Control
# ═══════════════════════════════════════════════════════════════════════════════

def set_url_verification(enabled: bool):
    """Enable or disable URL verification with Dymo API"""
    _url_verifier.set_enabled(enabled)

def is_url_verification_enabled() -> bool:
    """Check if URL verification is enabled"""
    return _url_verifier.is_enabled()

def is_url_verification_available() -> bool:
    """Check if URL verification is available (Dymo API key configured)"""
    return _url_verifier.is_available()

def get_url_verifier():
    """Get the URL verifier instance"""
    return _url_verifier

# ═══════════════════════════════════════════════════════════════════════════════
# Global Instances
# ═══════════════════════════════════════════════════════════════════════════════

web_fetcher = _fetcher
web_searcher = _searcher
url_verifier = _url_verifier