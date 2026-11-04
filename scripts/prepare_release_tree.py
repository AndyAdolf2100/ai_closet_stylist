"""Stage runtime and synthetic images; include four comparison images only when explicitly enabled."""
import argparse
import shutil
from pathlib import Path

from package_deployment import ROOT, release_files

DEMO_IMAGES = [f'{v}-{page}.png' for v in ['ios', 'yijian'] for page in ['home', 'profile', 'agent']] + [
    'yijian-home-feed.png', 'yijian-profile-identity.png', 'yijian-profile-services.png',
    'twin-private-female.png', 'twin-private-male.png', 'composer-attachments.png']


def prepare(destination, demos, include_comparison_evidence=False):
    if destination.exists():
        raise ValueError('Refusing to overwrite an existing release tree')
    for name in DEMO_IMAGES:
        if not (demos / name).is_file():
            raise ValueError('Missing synthetic screenshot: ' + name)
    for source in release_files(ROOT):
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    target = destination / 'stylist/static/closet-app/comparison/evolution/screenshots/demo'
    target.mkdir(parents=True, exist_ok=True)
    for name in DEMO_IMAGES:
        shutil.copyfile(demos / name, target / name)
    evidence = [f'{version}-home-populated{suffix}.png' for version in ['ios', 'yijian'] for suffix in ['', '-feed']]
    if include_comparison_evidence:
        for name in evidence:
            shutil.copyfile(ROOT / 'stylist/static/closet-app/comparison/evolution/screenshots/private' / name, target / name)
    for relative in ['stylist/static/closet-app/comparison/index.html', 'stylist/static/closet-app/comparison/evolution/index.html']:
        page = destination / relative
        html = page.read_text().replace('screenshots/private/', 'screenshots/demo/')
        html = html.replace('iOS 2.0.0 · 原生截图', 'iOS风格HTML参考 · 非原生截图')
        html = html.replace('当前爱搭衣橱 · 登录后截图', '当前爱搭衣橱 · 示例账号截图')
        html = html.replace('登录后首页搭配列表', '示例首页列表空态')
        html = html.replace('展开查看爱搭衣橱首页实际搭配内容', '展开查看爱搭衣橱首页示例内容')
        html = html.replace('iOS 2.0.0保留原生对照截图。', '部署包中iOS栏改用HTML参考截图，不代表原生截图；功能对比仍以dev_2.0.0源码为准。')
        marker = '<section class="ev" id="app-evolution">'
        html = html.replace(marker, marker + '<p class="ev-note">部署演示版：爱搭衣橱使用独立示例账号截图；iOS栏为HTML样式参考，不是2.0.0原生截图。原生账号截图仅在本机核对，不随包分发。</p>')
        html = html.replace('原生截图来自dev_2.0.0独立构建与iPhone 17模拟器；', '本机原生核对截图来自dev_2.0.0独立构建与iPhone 17模拟器，未随包分发；')
        html = html.replace('其他既有已登录截图保留本机证据', '本包所有演示截图均为合成数据；真实账号截图仅保留本机证据')
        if include_comparison_evidence:
            html = html.replace('本包所有演示截图均为合成数据；真实账号截图仅保留本机证据', '除用户指定的四张有数据首页对比截图外，其余部署截图使用合成示例')
            html = html.replace('部署演示版：爱搭衣橱使用独立示例账号截图；iOS栏为HTML样式参考，不是2.0.0原生截图。原生账号截图仅在本机核对，不随包分发。', '部署演示版：保留空态示例，另附用户指定的有数据首页截图；iOS有数据栏为HTML参考，不是2.0.0原生截图。交互演示不调用账号接口。')
        else:
            # Private evidence is optional; never leave broken image links in public releases.
            import re
            html = re.sub(r'<section class="ev-populated">.*?</section>', '', html, flags=re.S)
        page.write_text(html)
    shutil.copyfile(ROOT / '.dockerignore', destination / '.dockerignore')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--demos', type=Path, default=ROOT / 'var/release-demo')
    parser.add_argument('--include-comparison-evidence', action='store_true', help='Include only the four user-authorized populated-home screenshots; never credentials')
    args = parser.parse_args()
    prepare(args.destination, args.demos, args.include_comparison_evidence)
    print('Prepared release tree:', args.destination)
