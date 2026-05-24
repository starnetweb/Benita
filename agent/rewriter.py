"""
Claude-powered SEO/AEO blog post rewriter.
Produces Yoast-SEO-ready content with schema, FAQ, headings, and links.
"""
import json
import logging
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MIN_WORDS = int(os.getenv("MIN_WORD_COUNT", "320"))

SYSTEM_PROMPT = """You are an expert Nigerian education blogger and SEO specialist.
You write helpful, friendly, and accurate blog posts for JAMB/SSCE/UTME candidates
and Nigerian students seeking university or polytechnic admission.

Your writing style:
- Warm, encouraging, and relatable to Nigerian students aged 16-25
- Conversational but professional
- Use simple English â€” not too academic
- Include practical advice, not just news
- Use Nigerian context (mention JAMB, WAEC, NECO, NUC, etc. correctly)
- Never plagiarise â€” always write in your own voice based on the facts

SEO/AEO requirements you MUST follow:
- Use the focus keyphrase naturally in the first paragraph, at least one H2, and the meta description
- All H2/H3 headings must be keyword-rich and describe the section
- Include a FAQ section with 2-3 questions only (boosts featured snippets / AEO)
- Write at least """ + str(MIN_WORDS) + """ words
- Include transition words (however, therefore, furthermore, in addition, etc.)
- Use passive and active voice mix (Yoast readability score friendly)
- External links: cite the original sources with proper anchor text
- Internal link placeholders: add [INTERNAL_LINK: topic] where relevant
- Image suggestions: add [IMAGE: description] placeholders where images would help
- Schema markup: include Article + FAQPage schema JSON-LD
"""

BLOG_POST_PROMPT = """Based on the following news headlines and content, write a complete SEO-optimised blog post.

## INPUT NEWS DATA
{news_data}

## OUTPUT FORMAT (respond with valid JSON only â€” no markdown wrapper)
{{
  "seo_title": "...",
  "focus_keyphrase": "...",
  "meta_description": "...",
  "slug": "...",
  "content_html": "...",
  "schema_markup": {{...}},
  "word_count": 0,
  "tags": ["...", "..."],
  "categories": ["Education", "JAMB"],
  "excerpt": "..."
}}

## REQUIREMENTS FOR content_html:
- Start with an engaging introduction paragraph containing the focus keyphrase
- Use <h2> and <h3> tags for headings
- Use <p> for paragraphs
- Use <ul><li> or <ol><li> for lists
- Include a <div class="faq-section"> with Q&A pairs wrapped in <div class="faq-item"><h3 class="faq-question">...</h3><p class="faq-answer">...</p></div>
- Add [IMAGE: description] placeholders inline where images would help
- Add [INTERNAL_LINK: topic] for internal linking opportunities
- External source links: use <a href="SOURCE_URL" rel="noopener noreferrer" target="_blank">anchor text</a>
- End with a strong Call To Action encouraging students to check official JAMB portal or share with friends
- Write between {min_words} and {max_words} words — be concise, no padding, no repetition

## REQUIREMENTS FOR seo_title:
- Max 60 characters
- Include the current year (2025 or 2026 as appropriate) if relevant
- Include the focus keyphrase

## REQUIREMENTS FOR meta_description:
- 120-160 characters
- Include the focus keyphrase
- Write it as a benefit statement (e.g. "Find out how to...")

## REQUIREMENTS FOR slug:
- Lowercase, hyphens only, max 60 chars
- Based on the focus keyphrase

## REQUIREMENTS FOR schema_markup:
Include BOTH Article schema and FAQPage schema:
{{
  "@context": "https://schema.org",
  "@graph": [
    {{
      "@type": "Article",
      "headline": "...",
      "description": "...",
      "keywords": ["...", "..."],
      "datePublished": "{date_published}",
      "dateModified": "{date_published}",
      "author": {{"@type": "Organization", "name": "YourBlogName"}},
      "publisher": {{"@type": "Organization", "name": "YourBlogName"}},
      "inLanguage": "en-NG",
      "about": {{"@type": "Thing", "name": "JAMB Admission Nigeria"}}
    }},
    {{
      "@type": "FAQPage",
      "mainEntity": [
        {{"@type": "Question", "name": "...", "acceptedAnswer": {{"@type": "Answer", "text": "..."}}}}
      ]
    }}
  ]
}}
"""


def _build_news_data(articles: list[dict]) -> str:
    parts = []
    for i, art in enumerate(articles, 1):
        parts.append(f"""--- Article {i} ---
Title: {art['title']}
Source: {art.get('source_name', 'Unknown')}
URL: {art.get('url', '')}
Published: {art.get('published_at', 'Unknown')}
Summary: {art.get('summary', '')[:500]}
Full Content:
{art.get('full_content', '')[:3000]}
""")
    return "\n".join(parts)


def rewrite_articles(articles: list[dict]) -> dict:
    """
    Take 1-5 related articles and produce a single SEO blog post dict.
    Returns the parsed JSON output from Claude.
    """
    news_data = _build_news_data(articles)
    date_published = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    prompt = BLOG_POST_PROMPT.format(
        news_data=news_data,
        min_words=MIN_WORDS,
        max_words=int(MIN_WORDS * 1.3),
        date_published=date_published,
    )

    # Use custom prompt from DB if set, otherwise fall back to built-in
    try:
        import db as _db
        custom_prompt = _db.get_setting("rewriter_prompt", "")
        min_words_db  = int(_db.get_setting("min_word_count", str(MIN_WORDS)))
        system_prompt = custom_prompt.strip() if custom_prompt.strip() else SYSTEM_PROMPT
        if min_words_db != MIN_WORDS:
            prompt = BLOG_POST_PROMPT.format(
                news_data=news_data,
                min_words=min_words_db,
                max_words=int(min_words_db * 1.3),
                date_published=date_published,
            )
    except Exception:
        system_prompt = SYSTEM_PROMPT

    logger.info(f"Sending {len(articles)} articles to Claude for rewriting...")

    try:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Strip any accidental markdown code fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)
        logger.info(f"Claude produced post: '{data.get('seo_title', '')[:60]}' "
                    f"~{data.get('word_count', 0)} words")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON: {e}\nRaw: {raw[:500]}")
        raise
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise


def count_words(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    return len(text.split())


def validate_post(post: dict) -> list[str]:
    """Return list of SEO issues found."""
    issues = []
    title = post.get("seo_title", "")
    meta = post.get("meta_description", "")
    keyphrase = post.get("focus_keyphrase", "").lower()
    content = post.get("content_html", "")
    wc = post.get("word_count") or count_words(content)

    if len(title) > 60:
        issues.append(f"SEO title too long: {len(title)} chars (max 60)")
    if keyphrase and keyphrase not in title.lower():
        issues.append("Focus keyphrase missing from SEO title")
    if not (120 <= len(meta) <= 160):
        issues.append(f"Meta description length {len(meta)} (target 120-160)")
    if keyphrase and keyphrase not in meta.lower():
        issues.append("Focus keyphrase missing from meta description")
    if wc < MIN_WORDS:
        issues.append(f"Word count too low: {wc} (min {MIN_WORDS})")
    if "faq-section" not in content.lower():
        issues.append("FAQ section missing from content")
    if "<h2" not in content.lower():
        issues.append("No H2 headings found in content")

    return issues


def group_articles_by_topic(articles: list[dict]) -> list[list[dict]]:
    """
    Group articles into topic clusters for batched rewriting.
    Simple keyword-based grouping â€” up to 3 articles per group.
    """
    topic_keywords = {
        "registration": ["registr", "portal", "form", "apply"],
        "result": ["result", "score", "mark", "grade", "check"],
        "post_utme": ["post-utme", "post utme", "screening", "cut-off", "cutoff"],
        "admission": ["admission", "offered", "clearance", "caps", "accept"],
        "general_jamb": ["jamb", "utme", "cbt", "examination"],
    }

    groups: dict[str, list[dict]] = {k: [] for k in topic_keywords}
    groups["other"] = []

    for art in articles:
        text = (art.get("title", "") + " " + art.get("summary", "")).lower()
        placed = False
        for topic, kws in topic_keywords.items():
            if any(kw in text for kw in kws):
                if len(groups[topic]) < 3:
                    groups[topic].append(art)
                    placed = True
                    break
        if not placed:
            if len(groups["other"]) < 3:
                groups["other"].append(art)

    return [g for g in groups.values() if g]
