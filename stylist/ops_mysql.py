"""Exact phone-to-ID lookup in the original user domain, in a read-only transaction."""
from contextlib import suppress
from urllib.parse import unquote, urlsplit

import pymysql

from .errors import StylistError


def resolve_mobile(dsn, mobile):
    if not dsn:
        raise StylistError('ops_mysql_not_configured', '尚未配置只读MySQL查询连接；可以切换用户ID查询。', 503)
    try:
        target = urlsplit(dsn)
        database = unquote(target.path.lstrip('/'))
        if target.scheme != 'mysql' or not target.hostname or not target.username or not database:
            raise ValueError()
        options = dict(host=target.hostname, port=target.port or 3306, user=unquote(target.username),
                       password=unquote(target.password or ''), database=database,
                       connect_timeout=5, read_timeout=5, write_timeout=5, charset='utf8mb4',
                       autocommit=False, cursorclass=pymysql.cursors.DictCursor)
    except ValueError:
        raise StylistError('ops_mysql_not_configured', 'MySQL查询连接配置无效；可以切换用户ID查询。', 503) from None
    connection = None
    try:
        connection = pymysql.connect(**options)
        with connection.cursor() as cursor:
            cursor.execute('START TRANSACTION READ ONLY')
            # Match the Server user repository: deregistered users (status=3) are excluded.
            cursor.execute('SELECT id FROM `user` WHERE mobile=%s AND status<>%s ORDER BY id DESC LIMIT 2',
                           (mobile, 3))
            rows = cursor.fetchall()
    except pymysql.MySQLError:
        raise StylistError('ops_mysql_unavailable', '手机号查询暂不可用，请核对MySQL连接；也可以切换用户ID查询。', 503) from None
    finally:
        if connection:
            with suppress(pymysql.MySQLError):
                connection.rollback()
            with suppress(pymysql.MySQLError):
                connection.close()
    if not rows:
        raise StylistError('ops_mobile_not_found', '没有找到该手机号对应的有效账号。', 404)
    if len(rows) != 1:
        raise StylistError('ops_mobile_ambiguous', '该手机号对应多个有效账号，请改用用户ID查询。', 409)
    user_id = str(rows[0].get('id', ''))
    if not user_id.isdecimal() or int(user_id) < 1 or len(user_id) > 20:
        raise StylistError('ops_user_invalid', '手机号查询返回的用户ID无效。', 502)
    return user_id
