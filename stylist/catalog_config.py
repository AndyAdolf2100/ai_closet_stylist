"""Read-only system KB configuration; reuse local legacy settings without importing its app."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit


def boolean(value, default=False):
    return default if value is None else str(value).lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class CatalogConfig:
    enabled: bool = False
    ak: str = field(default='', repr=False)
    sk: str = field(default='', repr=False)
    host: str = 'api-knowledgebase.mlp.cn-beijing.volces.com'
    region: str = 'cn-beijing'
    service: str = 'air'
    collection: str = field(default='', repr=False)
    project: str = 'default'
    document_field: str = 'doc_id'
    document: str = field(default='', repr=False)
    dense_weight: float = .5
    rerank: bool = False
    rerank_model: str = 'base-multilingual-rerank'
    model: str = ''
    model_version: str = ''
    timeout: float = 15

    @property
    def available(self):
        host = urlsplit('https://' + self.host)
        # Fixed provider host family; never send service credentials to model-selected URLs.
        return bool(self.enabled and self.ak and self.sk and self.collection and self.document
                    and not self.document.removeprefix('doc_id_').isdecimal()
                    and host.hostname and host.hostname.endswith('.volces.com')
                    and host.netloc == host.hostname and host.path == '' and not host.query and not host.fragment)

    @classmethod
    def load(cls, raw):
        base = raw.get('db_knowledge') or raw.get('knowledge_base') or {}
        cfg = {**base, **((base.get('profiles') or {}).get('legacy') or {})}
        signing, filters, search = (cfg.get(name) or {} for name in ('signing', 'filter', 'search'))
        ak, sk = cfg.get('ak') or '', cfg.get('sk') or ''
        return cls(enabled=boolean(cfg.get('enabled'), bool(ak and sk)), ak=ak, sk=sk,
                   host=cfg.get('api_endpoint') or cls.host, region=signing.get('region') or cls.region,
                   service=signing.get('service') or cls.service, collection=cfg.get('collection_name') or '',
                   project=cfg.get('project') or 'default', document_field=filters.get('doc_id_field') or cfg.get('doc_id_field') or 'doc_id',
                   document=filters.get('doc_id_value') or cfg.get('doc_id_value') or '',
                   dense_weight=float(search.get('dense_weight', .5)), rerank=boolean(search.get('rerank_enabled')),
                   rerank_model=search.get('rerank_model') or cls.rerank_model,
                   model=cfg.get('default_model') or '', model_version=cfg.get('default_model_version') or '',
                   timeout=min(30, max(1, float(cfg.get('timeout_s', 15)))))
