"""Build isolated markup/styles for the App's direct Agent component mount."""
import re
from pathlib import Path

static = Path(__file__).resolve().parents[1] / 'stylist/static'
source = (static / 'index.html').read_text()
body = source.split('<body>', 1)[1].split('</body>', 1)[0]
body = re.sub(r'<script\b[^>]*>.*?</script>', '', body, flags=re.S)
body = body.replace('id="checkin-entry-label">对话签到', 'id="checkin-entry-label">每日签到')
body = body.replace('id="checkin-entry-meta">+10 体验积分', 'id="checkin-entry-meta">查看签到奖励')
(static / 'closet-app/agent-fragment.html').write_text(body.rstrip() + '\n')
styles = ['style.css', 'outfit-board.css', 'checkin.css', 'memory.css', 'wardrobe-journey.css',
          'companion-characters.css', 'companion-loading.css', 'system-colors.css']
parts = []
for name in styles:
    css = (static / name).read_text().replace(':root', ':scope')
    css = re.sub(r'(?<![\w-])(?:html|body)(?=[\s.#:\[>{,])', ':scope', css)
    css = css.replace("url('assets/", "url('/static/assets/").replace('url("assets/', 'url("/static/assets/')
    parts.append(f'/* {name} */\n{css}')
(static / 'closet-app/agent-scoped.css').write_text('@scope (#yijian-agent-root) {\n' + '\n'.join(parts) + '\n}\n')
print('Built direct Agent fragment and scoped component styles')
