from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.main import create_app

CID = 'sty_' + 'a' * 32


def test_ops_page_is_standalone_and_packagable(tmp_path):
    with TestClient(create_app(Settings(database=str(tmp_path/'ops.db')))) as client:
        page = client.get('/ops/conversations')
        assert page.status_code == 200 and '消息记录' in page.text
        assert '/static/ops/console.js' in page.text
        assert client.get('/static/ops/reply-view.js').status_code == 200
        assert client.get('/static/ops/console.css').status_code == 200
        assert 'ops/conversations' not in client.get('/app/').text


def test_ops_fixed_read_only_routes_validate_and_check_ownership(tmp_path, monkeypatch):
    calls = []

    async def fake(settings, path, params=None):
        calls.append((path, params))
        if '/users/' in path:
            return {'user_id':'1024','conversations':[], 'total':0}
        return {'conversation_id':CID,'session':{'owner_id':'1024'},'messages':[],'requests':[]}
    monkeypatch.setattr('stylist.ops_records.read_records',fake)
    with TestClient(create_app(Settings(database=str(tmp_path/'read.db')))) as client:
        base='/stylist-api/ops/records'
        result=client.get(base+'/users/1024/conversations?limit=1&include_deleted=true')
        assert result.status_code == 200 and result.headers['cache-control']=='no-store'
        assert calls[-1][1]=={'limit':1,'offset':0,'include_deleted':'true'}
        assert client.get(base+'/conversations/'+CID+'?user_id=1024').status_code == 200
        assert client.get(base+'/conversations/'+CID+'?user_id=2048').status_code == 409
        assert client.get(base+'/users/0/conversations').status_code == 422
        assert client.get(base+'/users/1024/conversations?limit=101').status_code == 422
        assert client.get(base+'/conversations/not-valid?user_id=1024').status_code == 422
        assert client.post(base+'/users/1024/conversations',json={}).status_code == 405


def test_ops_upstream_failures_do_not_turn_into_empty_history(tmp_path, monkeypatch):
    from stylist.errors import StylistError

    async def unavailable(*args, **kwargs):
        raise StylistError('ops_records_unavailable','查询连接失败',503)
    monkeypatch.setattr('stylist.ops_records.read_records',unavailable)
    with TestClient(create_app(Settings(database=str(tmp_path/'fail.db')))) as client:
        response=client.get('/stylist-api/ops/records/users/1024/conversations')
        assert response.status_code==503 and response.json()['code']=='ops_records_unavailable'


def test_ops_preserves_bad_message_fragments_for_local_ui_errors(tmp_path, monkeypatch):
    async def fake(*args, **kwargs):
        return {'conversation_id':CID,'session':{'owner_id':'1024'},
                'messages':[{'version':1,'reply':'{bad-json'}], 'requests':{'unexpected':'object'}}
    monkeypatch.setattr('stylist.ops_records.read_records',fake)
    with TestClient(create_app(Settings(database=str(tmp_path/'partial.db')))) as client:
        response=client.get('/stylist-api/ops/records/conversations/'+CID+'?user_id=1024')
        assert response.status_code==200
        assert response.json()['messages'][0]['reply']=='{bad-json'
        assert response.json()['requests']=={'unexpected':'object'}


def test_phone_lookup_is_read_only_masked_and_validated(tmp_path, monkeypatch):
    calls=[]
    def fake(dsn,mobile):
        calls.append((dsn,mobile))
        return '1024'
    monkeypatch.setattr('stylist.ops_records.resolve_mobile',fake)
    with TestClient(create_app(Settings(database=str(tmp_path/'mobile.db'),ops_mysql_dsn='synthetic-private'))) as client:
        response=client.get('/stylist-api/ops/records/resolve-user?mobile=13800000000')
        assert response.status_code==200
        assert response.json()=={'user_id':'1024','mobile_masked':'138****0000'}
        assert response.headers['cache-control']=='no-store'
        assert calls==[('synthetic-private','13800000000')]
        assert client.get('/stylist-api/ops/records/resolve-user?mobile=123').status_code==422
