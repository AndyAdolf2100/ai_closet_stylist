"""Read-only MySQL account lookup and fixed bridge to Server conversation records."""
import asyncio

import httpx
from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse

from .errors import StylistError
from .ops_mysql import resolve_mobile

USER_PATTERN = r'^[1-9][0-9]{0,19}$'
CONVERSATION_PATTERN = r'^sty_[a-f0-9]{32}$'


async def read_records(settings, path, params=None):
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout, trust_env=False,
                                     follow_redirects=False) as client:
            response = await client.get(settings.server_url.rstrip('/') + path, params=params)
        if response.status_code == 404:
            raise StylistError('ops_records_not_found', '会话不存在，或Server尚未提供查询接口。', 404)
        if response.status_code != 200:
            raise StylistError('ops_records_unavailable', 'Server会话查询暂不可用，请核对服务和只读数据库配置。', 503)
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError()
        return payload
    except (httpx.HTTPError, ValueError):
        raise StylistError('ops_records_unavailable', 'Server会话查询连接失败或响应异常，请稍后重试。', 503) from None


def router(settings):
    routes = APIRouter(prefix='/stylist-api/ops/records')

    @routes.get('/resolve-user')
    async def resolve_user(mobile: str = Query(pattern=r'^1[3-9][0-9]{9}$')):
        user_id = await asyncio.to_thread(resolve_mobile, settings.ops_mysql_dsn, mobile)
        return JSONResponse({'user_id': user_id, 'mobile_masked': mobile[:3] + '****' + mobile[-4:]},
                            headers={'Cache-Control': 'no-store'})

    @routes.get('/users/{user_id}/conversations')
    async def conversations(user_id: str = Path(pattern=USER_PATTERN),
                            limit: int = Query(default=20, ge=1, le=100),
                            offset: int = Query(default=0, ge=0), include_deleted: bool = False):
        payload = await read_records(settings,
            f'/api/internal/stylist/records/users/{user_id}/conversations',
            {'limit': limit, 'offset': offset, 'include_deleted': str(include_deleted).lower()})
        if str(payload.get('user_id')) != user_id or not isinstance(payload.get('conversations'), list):
            raise StylistError('ops_records_invalid', '会话列表与查询用户不一致或格式异常。', 502)
        return JSONResponse(payload, headers={'Cache-Control': 'no-store'})

    @routes.get('/conversations/{conversation_id}')
    async def detail(conversation_id: str = Path(pattern=CONVERSATION_PATTERN),
                     user_id: str = Query(pattern=USER_PATTERN)):
        payload = await read_records(settings, f'/api/internal/stylist/records/conversations/{conversation_id}')
        session = payload.get('session')
        if not isinstance(session, dict):
            raise StylistError('ops_records_invalid', '会话归属信息格式异常，暂不展示详情。', 502)
        if (payload.get('conversation_id') != conversation_id
                or str(session.get('owner_id')) != user_id):
            raise StylistError('ops_records_mismatch', '该会话与当前查询用户不一致，请重新选择。', 409)
        return JSONResponse(payload, headers={'Cache-Control': 'no-store'})

    return routes
