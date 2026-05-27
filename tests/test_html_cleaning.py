from bs4 import BeautifulSoup

from yclib_extract.lib.html_cleaning import (
    extract_author_info,
    extract_main_content,
    extract_transcript_section,
    html_to_markdown,
    process_footnotes,
)


def test_process_footnotes_multi_line_and_references():
    markdown = """
Driven by people's identities. [1]

**Notes**

[1]
Line one
Line two
Line three

[2]
Another footnote
"""
    processed = process_footnotes(markdown)

    # Check reference replacement
    assert "identities. [^1]" in processed
    # Check footnote definition format
    assert "[^1]: Line one Line two Line three" in processed
    assert "[^2]: Another footnote" in processed
    # Check that original definition was removed from body
    assert "[1]\nLine one" not in processed


def test_process_footnotes_inline_and_same_line():
    markdown = "Body text [1].\n\n**Notes**\n\n[1] Footnote on same line."
    processed = process_footnotes(markdown)

    assert "Body text [^1]." in processed
    assert "[^1]: Footnote on same line." in processed


def test_process_footnotes_empty_line_in_content():
    markdown = """
Body [1].

**Notes**

[1]
Line one

Line two

[2]
Next
"""
    processed = process_footnotes(markdown)
    assert "[^1]: Line one Line two" in processed
    assert "[^2]: Next" in processed


def test_html_to_markdown_removes_chrome_and_preserves_formatting():
    html = """
    <html>
      <body>
        <nav>Navigation</nav>
        <header>Header</header>
        <article>
          <h1>Title</h1>
          <p>Hello <strong>world</strong> and <em>friends</em>.</p>
        </article>
        <footer>Footer</footer>
      </body>
    </html>
    """

    markdown = html_to_markdown(html)

    assert "Navigation" not in markdown
    assert "Header" not in markdown
    assert "Footer" not in markdown
    assert "# Title" in markdown
    assert "**world**" in markdown
    assert "*friends*" in markdown


def test_extract_main_content_prefers_article_then_body():
    soup = BeautifulSoup(
        """
        <html>
          <body>
            <main>Main content</main>
            <article>Article content</article>
          </body>
        </html>
        """,
        "html.parser",
    )

    assert extract_main_content(soup) == "<article>Article content</article>"


def test_extract_transcript_section_finds_common_container():
    soup = BeautifulSoup(
        '<div class="transcript">Line one<br/>Line two</div>',
        "html.parser",
    )

    assert extract_transcript_section(soup) == "Line one\nLine two"


def test_extract_author_info_reads_meta_and_class_names():
    meta_soup = BeautifulSoup('<meta name="author" content="Ada Lovelace" />', "html.parser")
    class_soup = BeautifulSoup('<div class="creator">Grace Hopper</div>', "html.parser")

    assert extract_author_info(meta_soup) == "Ada Lovelace"
    assert extract_author_info(class_soup) == "Grace Hopper"
