import pytest

from stylist.errors import StylistError
from stylist.ops_mysql import resolve_mobile

DSN = 'mysql://synthetic:private%40value@127.0.0.1:3306/fixture'


def fake_connection(monkeypatch, rows):
    events=[]
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,*args):events.append(args)
        def fetchall(self):return rows
    class Connection:
        def cursor(self):return Cursor()
        def rollback(self):events.append('rollback')
        def close(self):events.append('close')
    def connect(**options):
        assert options['password']=='private@value' and options['database']=='fixture'
        assert options['autocommit'] is False
        return Connection()
    monkeypatch.setattr('stylist.ops_mysql.pymysql.connect',connect)
    return events


def test_phone_mapping_uses_bound_select_and_read_only_transaction(monkeypatch):
    events=fake_connection(monkeypatch,[{'id':1024}])
    assert resolve_mobile(DSN,'13800000000')=='1024'
    assert events[0]==('START TRANSACTION READ ONLY',)
    assert events[1][0].startswith('SELECT id FROM `user`')
    assert events[1][1]==('13800000000',3)
    assert events[-2:]==['rollback','close']


@pytest.mark.parametrize('rows,code',[([], 'ops_mobile_not_found'),([{'id':1},{'id':2}],'ops_mobile_ambiguous'),([{'id':0}],'ops_user_invalid')])
def test_missing_ambiguous_and_invalid_accounts_are_not_silently_chosen(monkeypatch,rows,code):
    events=fake_connection(monkeypatch,rows)
    with pytest.raises(StylistError,match=code):
        resolve_mobile(DSN,'13800000000')
    assert events[-2:]==['rollback','close']


def test_unconfigured_lookup_never_connects(monkeypatch):
    monkeypatch.setattr('stylist.ops_mysql.pymysql.connect',lambda **kwargs:pytest.fail('must not connect'))
    with pytest.raises(StylistError,match='ops_mysql_not_configured'):
        resolve_mobile('','13800000000')
