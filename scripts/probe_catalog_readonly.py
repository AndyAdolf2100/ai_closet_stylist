"""Explicit signed system-KB metadata probe; no account history, LLM, image, or business writes."""
import argparse
import asyncio
import json

from stylist.catalog import CATEGORIES, CatalogSearch
from stylist.catalog_retrieval import category_conflicts
from stylist.config import Settings
from stylist.errors import StylistError
from stylist.models import Task
from stylist.policy import suitability
from stylist.retrieval import from_row


async def probe(gender, categories):
    search = CatalogSearch(Settings.load().catalog)
    task = Task(gender=gender, source='hybrid', weather_policy='ignored')
    results = []
    for category in categories:
        try:
            rows = await search.search(query=f'{gender}士日常穿搭 {category}', category=category, gender=gender, limit=8)
            products = [from_row(row, 'system') for row in rows]
            usable = [p for p in products if p and not category_conflicts(p) and not suitability(p, task)[0]]
            results.append({'category': category, 'returned': len(rows), 'usable_metadata': len(usable),
                            'missing_images': sum(not p.original_image and not p.cutout_image for p in usable)})
        except StylistError as exc:
            results.append({'category': category, 'error': exc.code})
    print(json.dumps({'scope': 'signed_system_kb_metadata_only', 'results': results,
                      'server_resolve_verified': False, 'model_called': False, 'writes': False}, ensure_ascii=False))
    return int(any('error' in row for row in results))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-readonly', action='store_true')
    parser.add_argument('--gender', choices=['男', '女'], required=True)
    parser.add_argument('--categories', nargs='+', choices=CATEGORIES, default=['上衣', '裤子', '鞋子'])
    args = parser.parse_args()
    if not args.live_readonly:
        parser.error('Real signed queries require explicit --live-readonly')
    raise SystemExit(asyncio.run(probe(args.gender, args.categories)))


if __name__ == '__main__':
    main()
