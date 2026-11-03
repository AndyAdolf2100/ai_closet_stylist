"""Fixed, signed, system-document-only VikingDB search. Never reads personal KB documents."""
import json
import re

import httpx

from .catalog_signing import SigningContext, sign_request
from .errors import StylistError

SEARCH_PATH = '/api/knowledge/collection/search_knowledge'
CATEGORIES = ('上衣', '裤子', '裙子', '连衣裙', '连体衣', '外套', '鞋子', '包包', '配饰', '首饰', '帽子')


def business_id(row):
    # The enclosing chunk id is NOT a business product id.
    for field in ('product_id', 'id'):
        value = str(row.get(field) or '').strip()
        if value.isdecimal() and 0 < int(value) < 10**20:
            return str(int(value))
    return None


def parse_chunk(chunk):
    row = {}
    for field in chunk.get('table_chunk_fields') or []:
        key = field.get('field_name') or field.get('name')
        if key:
            row[key] = field.get('field_value') if 'field_value' in field else field.get('value')
    if not row:
        for line in str(chunk.get('content') or '').splitlines():
            found = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:：]\s*(.+?)\s*$', line)
            if found:
                row[found[1]] = found[2]
    identity = business_id(row)
    if identity is None:
        return None
    row['product_id'] = identity
    row['source'] = 'system'
    row['_kb_document'] = (chunk.get('doc_info') or {}).get('doc_id')
    return row


class CatalogSearch:
    def __init__(self, config, transport=None):
        self.config, self.transport = config, transport

    async def search(self, *, query, category, gender, limit):
        cfg = self.config
        if not cfg.available:
            raise StylistError('catalog_not_configured', '系统参考衣橱暂未接通。')
        if category not in CATEGORIES or gender not in {None, '男', '女', '男女同款'}:
            raise StylistError('catalog_query_invalid', '系统参考衣橱查询条件无效。', 400)
        clauses = [{'op': 'must', 'field': cfg.document_field, 'conds': [cfg.document]},
                   {'op': 'must', 'field': 'class_name', 'conds': [category]}]
        if gender:
            clauses.append({'op': 'must', 'field': 'gender', 'conds': list(dict.fromkeys([gender, '男女同款']))})
        payload = {'name': cfg.collection, 'project': cfg.project, 'query': query[:1200],
                   'limit': min(32, max(1, int(limit))), 'dense_weight': cfg.dense_weight,
                   'query_param': {'doc_filter': {'op': 'and', 'conds': clauses}}}
        if cfg.model:
            payload['model'] = cfg.model
        if cfg.model_version:
            payload['model_version'] = cfg.model_version
        if cfg.rerank:
            payload['post_processing'] = {'rerank_switch': True, 'rerank_model': cfg.rerank_model}
        body = json.dumps(payload, ensure_ascii=False).encode()
        headers = sign_request(SigningContext(cfg.ak, cfg.sk, cfg.region, cfg.service),
                               'POST', cfg.host, SEARCH_PATH, body)
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout, trust_env=False, follow_redirects=False,
                                         transport=self.transport) as client:
                response = await client.post('https://' + cfg.host + SEARCH_PATH, content=body, headers=headers)
                response.raise_for_status()
                result = response.json()
            if not isinstance(result, dict) or result.get('code', 0) != 0:
                raise ValueError('invalid KB response')
            data = result.get('data')
            if not isinstance(data, dict) or not isinstance(data.get('result_list', []), list):
                raise ValueError('invalid KB response')
            rows = []
            for chunk in data.get('result_list', [])[:32]:
                if not isinstance(chunk, dict):
                    continue
                row = parse_chunk(chunk)
                if row is not None:
                    # A wrong document is a provider-boundary error, never a candidate.
                    if row['_kb_document'] != cfg.document:
                        raise StylistError('catalog_source_mismatch', '系统参考衣橱返回范围异常。')
                    rows.append(row)
            return rows
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise StylistError('catalog_unavailable', '这次系统参考衣橱暂时没有查顺利。') from exc
