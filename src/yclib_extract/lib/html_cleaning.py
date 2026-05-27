import html as html_lib
import json
import re
from html.parser import HTMLParser
from typing import Dict, Optional
from urllib.parse import urlparse


class MarkdownHTMLParser(HTMLParser):
    """Convert HTML to Markdown preserving formatting."""

    def __init__(self):
        super().__init__()
        self.text = []
        self.stack = []
        self.link_href = None

    def handle_starttag(self, tag, attrs):
        if tag in ("b", "strong"):
            self.text.append("**")
            self.stack.append(tag)
        elif tag in ("i", "em"):
            self.text.append("*")
            self.stack.append(tag)
        elif tag == "a":
            href = next((v for k, v in attrs if k == "href"), None)
            if href:
                self.text.append("[")
                self.link_href = href
                self.stack.append("a")
        elif tag in ("h1", "h2", "h3", "h4"):
            level = int(tag[1])
            self.text.append(f"\n{'#' * level} ")
            self.stack.append(tag)
        elif tag == "li":
            self.text.append("- ")
            self.stack.append("li")
        elif tag == "br":
            self.text.append("\n")
        elif tag == "p":
            self.text.append("\n")
            self.stack.append("p")
        elif tag == "code":
            self.text.append("`")
            self.stack.append("code")

    def handle_endtag(self, tag):
        if tag in ("b", "strong", "i", "em", "code", "h1", "h2", "h3", "h4", "p", "li", "a"):
            if tag in ("b", "strong"):
                self.text.append("**")
            elif tag in ("i", "em"):
                self.text.append("*")
            elif tag == "code":
                self.text.append("`")
            elif tag == "a" and self.link_href:
                self.text.append(f"]({self.link_href})")
                self.link_href = None
            elif tag in ("h1", "h2", "h3", "h4"):
                self.text.append("\n")
            elif tag in ("p", "li"):
                self.text.append("\n")
            
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()

    def handle_data(self, data):
        # Unescape entities like &#x27; to '
        self.text.append(html_lib.unescape(data))

    def get_markdown(self):
        return "".join(self.text).strip()


def _sanitize_content(html: str, base_url: str = "") -> str:
    """Remove YC chrome and extract main content."""
    # Remove YC-specific elements
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r'<[^>]*class="[^"]*ycdc-[^"]*"[^>]*>.*?</[^>]+>', "", html, flags=re.DOTALL)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL)

    return html


def html_to_markdown(html: str, base_url: str = "") -> str:
    """Convert HTML to clean Markdown."""
    html = _sanitize_content(html, base_url)
    parser = MarkdownHTMLParser()
    parser.feed(html)
    md = parser.get_markdown()

    # Cleanup extra whitespace
    md = re.sub(r"\n\n+", "\n\n", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    return md.strip()


def extract_main_content(soup) -> Optional[str]:
    """Extract main content from BeautifulSoup object."""
    data_page = soup.find(attrs={"data-page": True})
    if data_page:
        raw_payload = data_page.get("data-page") or ""
        try:
            payload = json.loads(html_lib.unescape(raw_payload))
            article = payload.get("props", {}).get("article", {})
        except (TypeError, ValueError, json.JSONDecodeError):
            article = {}

        title = article.get("title") or ""
        content = article.get("content") or ""
        transcript = article.get("transcript") or ""

        parts = []
        if title:
            parts.append(f"<h1>{html_lib.escape(title)}</h1>")
        if content:
            parts.append(f"<p>{html_lib.escape(content)}</p>")
        if transcript:
            transcript_chunks = [
                chunk.strip() for chunk in transcript.split("\n\n") if chunk.strip()
            ]
            if transcript_chunks:
                transcript_html = "".join(
                    f"<p>{html_lib.escape(chunk)}</p>" for chunk in transcript_chunks
                )
            else:
                transcript_html = f"<p>{html_lib.escape(transcript)}</p>"
            parts.append(f'<section class="transcript">{transcript_html}</section>')

        if parts:
            return "<article>" + "".join(parts) + "</article>"

    # Try common content containers
    targets = [
        ("div", "ycdc-toc-container"),
        ("article", None),
        ("main", None),
        ("div", "content"),
    ]

    for tag, cls in targets:
        if cls:
            elem = soup.find(tag, {"class": cls})
        else:
            elem = soup.find(tag)
        if elem:
            return str(elem)

    return str(soup.body) if soup.body else None


def extract_transcript_section(soup) -> Optional[str]:
    """Extract on-page transcript if present."""
    patterns = [
        ("div", "transcript"),
        ("section", "transcript"),
        ("div", "captions"),
    ]

    for tag, cls in patterns:
        elem = soup.find(tag, {"class": cls})
        if elem:
            return elem.get_text(separator="\n").strip()

    return None


def extract_author_info(soup) -> Optional[str]:
    """Extract author/company info from page metadata."""
    # Look for meta tags or author elements
    meta = soup.find("meta", {"name": "author"})
    if meta:
        return meta.get("content")

    # Try common author element classes
    author_elem = soup.find(["span", "div"], {"class": re.compile(r"author|creator")})
    if author_elem:
        return author_elem.get_text().strip()

    return None


def process_internal_links(
    markdown: str, blog_domain: str, url_to_slug_map: Optional[Dict[str, str]] = None
) -> str:
    """
    Convert internal blog links to markdown file references.

    External links remain as [text](url).
    Internal links to same blog become [text](./slug.md) or [text](#anchor) if available.

    Args:
        markdown: The markdown content with links
        blog_domain: Domain to match for internal links (e.g., 'blog.samaltman.com')
        url_to_slug_map: Optional mapping of URLs to file slugs for internal references

    Returns:
        Processed markdown with internal links converted to file references
    """
    if url_to_slug_map is None:
        url_to_slug_map = {}

    def replace_link(match):
        link_text = match.group(1)
        link_url = match.group(2)

        # Parse the link URL
        parsed = urlparse(link_url)

        # Check if it's internal (same blog domain)
        is_internal = (
            parsed.netloc.lower() == blog_domain.lower()
            or parsed.netloc.lower() == f"www.{blog_domain}".lower()
        )

        if is_internal and link_url in url_to_slug_map:
            # Convert to file reference
            slug = url_to_slug_map[link_url]
            return f"[{link_text}](./{slug}.md)"
        else:
            # Keep external links or unmapped internal links as is
            return f"[{link_text}]({link_url})"

    # Match markdown links: [text](url)
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    return re.sub(pattern, replace_link, markdown)


def process_footnotes(markdown: str) -> str:
    """
    Process footnotes in markdown text.
    
    Detects the "Notes" or "Footnotes" section at the end of the document,
    extracts footnote definitions from there, and converts inline [1] 
    references in the body to [^1].
    """
    # Find the Notes section. PG essays usually have a "**Notes**" header.
    # We look for a line that is roughly "Notes" or "Footnotes"
    lines = markdown.split("\n")
    notes_start_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip().lower()
        if stripped in ("**notes**", "notes", "**footnotes**", "footnotes"):
            notes_start_idx = i
            break
    
    # If no Notes section found, we still want to try to find footnote definitions
    # but we must be careful not to eat the body. 
    # Actually, for PG essays, they almost always have a Notes section.
    
    body_lines = lines[:notes_start_idx] if notes_start_idx != -1 else lines
    notes_lines = lines[notes_start_idx:] if notes_start_idx != -1 else []
    
    footnotes = {}
    footnote_indices = set()
    
    # Extract footnotes from the notes section
    i = 0
    while i < len(notes_lines):
        line = notes_lines[i]
        stripped = line.strip()
        
        match = re.match(r"^\[(\d+)\](?:\s+(.*))?$", stripped)
        if match:
            fn_num = match.group(1)
            fn_content = [match.group(2).strip()] if match.group(2) else []
            
            i += 1
            while i < len(notes_lines):
                next_line = notes_lines[i]
                next_stripped = next_line.strip()
                if re.match(r"^\[\d+\]", next_stripped):
                    break
                fn_content.append(next_stripped)
                i += 1
            
            full_text = " ".join(filter(None, fn_content))
            if full_text:
                footnotes[fn_num] = full_text
                footnote_indices.add(fn_num)
            continue
        i += 1

    # Replace inline references in body text
    result_body_lines = []
    for line in body_lines:
        # Check if line IS just a [number] that we found in footnotes
        # This happens in PG essays where [1] is on its own line after a <br>
        stripped = line.strip()
        is_fn_marker_line = False
        if re.match(r"^\[\d+\]$", stripped):
            fn_num = stripped[1:-1]
            if fn_num in footnote_indices:
                is_fn_marker_line = True
                # Replace the whole line with just the anchor
                line = line.replace(f"[{fn_num}]", f"[^{fn_num}]")

        if not is_fn_marker_line:
            # Normal line, do regex replacement
            for fn_num in sorted(footnote_indices, key=lambda x: int(x), reverse=True):
                pattern = rf"\[{re.escape(fn_num)}\](?!\()"
                replacement = f"[^{fn_num}]"
                line = re.sub(pattern, replacement, line)
        
        result_body_lines.append(line)

    result = "\n".join(result_body_lines).rstrip()

    if footnotes:
        result += "\n\n**Notes**\n\n"
        for fn_num in sorted(footnotes.keys(), key=lambda x: int(x)):
            result += f"[^{fn_num}]: {footnotes[fn_num]}\n"

    return result.strip()


def generate_enriched_frontmatter(metadata: dict, content: str) -> str:
    """Generate YAML frontmatter with enhanced metadata.
    
    Args:
        metadata: Source metadata (title, author, date, etc.)
        content: Extracted content body
        
    Returns:
        YAML frontmatter string
    """
    import yaml
    from datetime import datetime
    
    frontmatter = {
        'title': metadata.get('title', 'Untitled'),
        'author': metadata.get('author', 'Unknown'),
        'date': metadata.get('date', datetime.now().isoformat()),
        'source_url': metadata.get('url', ''),
        'tags': metadata.get('tags', []),
    }
    
    # Add content metrics
    frontmatter['word_count'] = len(content.split())
    frontmatter['reading_time_minutes'] = max(1, frontmatter['word_count'] // 250)
    
    # Add extraction metadata
    frontmatter['extracted_at'] = datetime.now().isoformat()
    frontmatter['extraction_quality'] = metadata.get('quality', 'unknown')
    
    return '---\n' + yaml.dump(frontmatter, default_flow_style=False) + '---\n'
