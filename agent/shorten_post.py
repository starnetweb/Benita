"""Rewrite an existing post shorter and update WordPress."""
import sqlite3, anthropic, requests, re, sys

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY')
DB_PATH  = os.getenv('DB_PATH', 'db/blogger.db')
API_BASE = os.getenv('WP_SITE_URL','').rstrip('/') + '/wp-json/wp/v2'
AUTH     = (os.getenv('WP_USERNAME'), os.getenv('WP_APP_PASSWORD'))
HEADERS  = {'Content-Type': 'application/json'}

wp_id = int(sys.argv[1]) if len(sys.argv) > 1 else 11447

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
post = dict(conn.execute('SELECT * FROM posts WHERE wp_post_id=?', (wp_id,)).fetchone())
conn.close()

print(f'Rewriting [{wp_id}]: {post["title"]}')
print(f'Current word count: {post["word_count"]}')

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
resp = client.messages.create(
    model='claude-haiku-4-5',
    max_tokens=2000,
    messages=[{
        'role': 'user',
        'content': (
            'Rewrite the following blog post to be concise and between 320-416 words total.\n\n'
            'Keep: same SEO intent, H2/H3 headings, FAQ with 2-3 questions, one CTA, external links.\n'
            'Remove: padding, repetition, filler, excessive bullets, [IMAGE:] and [INTERNAL_LINK:] placeholders.\n\n'
            'IMPORTANT: Return ONLY raw HTML. No markdown, no code fences, no backticks, no explanation. '
            'Start your response directly with an HTML tag like <p> or <h2>.\n\n'
            'ORIGINAL CONTENT:\n' + post['content']
        )
    }]
)

raw = resp.content[0].text.strip()
# Strip markdown code fences if model accidentally added them
raw = re.sub(r'^```[a-z]*\s*', '', raw, flags=re.IGNORECASE)
raw = re.sub(r'\s*```$', '', raw).strip()

word_count = len(re.sub(r'<[^>]+>', ' ', raw).split())
print(f'New word count: {word_count}')

wp_resp = requests.post(f'{API_BASE}/posts/{wp_id}', json={'content': raw}, auth=AUTH, headers=HEADERS, timeout=30)
wp_resp.raise_for_status()
print(f'WordPress updated OK')

conn = sqlite3.connect(DB_PATH)
conn.execute('UPDATE posts SET content=?, word_count=? WHERE wp_post_id=?', (raw, word_count, wp_id))
conn.commit()
conn.close()
print('Done.')
