"""Exercise deployment ordering/rollback with fake Docker/Nginx, never the real host."""
import hashlib
import json
import os
import pty
import select
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest

from scripts.package_deployment import FILES, package

ROOT = Path(__file__).resolve().parents[1]
COMMAND = r'''
import json, os, pathlib, shutil, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
root = pathlib.Path(os.environ['FAKE_HOST'])
with (root/'events').open('a') as f:
    f.write(json.dumps([name, args])+'\n')
if name == 'id': print('0')
elif name == 'uname': print('Linux' if args == ['-s'] else 'x86_64')
elif name == 'flock': pass
elif name == 'ss':
    if (root/'running').exists() or os.environ.get('FAIL_PORT'):
        print('LISTEN 0 128 127.0.0.1:8466 *:*')
elif name == 'mv':
    paths = [a for a in args if not a.startswith('-')]
    os.replace(paths[0], paths[1])
elif name == 'curl':
    if os.environ.get('FAIL_PROXY') and any(a.startswith('https:') for a in args):
        print('<html>old admin page</html>')
    else: print('{"ready": true}')
elif name == 'nginx':
    target = pathlib.Path(os.environ['AICLOSET_VHOST_DIR'])/'aicloset-assistant.wxbjq.top.conf'
    if args == ['-t'] and os.environ.get('FAIL_NGINX') and target.exists() and target.read_text().startswith('new site'):
        sys.exit(1)
elif name == 'docker':
    if args[:1] == ['ps']:
        if (root/'running').exists(): print('managed-container')
    elif args[:1] == ['build']:
        if os.environ.get('FAIL_BUILD'): sys.exit(1)
    elif args[:1] == ['compose'] and 'up' in args:
        if os.environ.get('FAIL_UP') and not (root/'up-failed').exists():
            (root/'up-failed').touch(); sys.exit(1)
        (root/'running').touch()
        (root/'image').write_text(os.environ['STYLIST_IMAGE'])
    elif args[:1] == ['compose'] and 'stop' in args:
        (root/'running').unlink(missing_ok=True)
else: sys.exit(9)
'''


@pytest.fixture
def host(tmp_path):
    commands = tmp_path / 'commands'
    commands.mkdir()
    for name in ['id', 'uname', 'flock', 'ss', 'mv', 'curl', 'nginx', 'docker']:
        path = commands / name
        path.write_text('#!' + sys.executable + '\n' + COMMAND)
        path.chmod(0o755)
    vhost = tmp_path / 'vhost'
    vhost.mkdir()
    env = {**os.environ, 'PATH': str(commands) + ':' + os.environ['PATH'], 'FAKE_HOST': str(tmp_path),
           'AICLOSET_DEPLOY_ROOT': str(tmp_path / 'deployment'), 'AICLOSET_VHOST_DIR': str(vhost),
           'AICLOSET_NGINX_BIN': str(commands / 'nginx'), 'STYLIST_LLM_KEY': 'synthetic-runtime$#key'}
    return tmp_path, env


def make_release(tmp_path, label, *, offline=False):
    source = tmp_path / ('source-' + label)
    for name in FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture ' + label)
    (source / 'install.sh').write_bytes((ROOT / 'install.sh').read_bytes())
    (source / 'deploy/nginx/aicloset-assistant.centos7.conf').write_text('new site ' + label)
    (source / 'stylist').mkdir()
    (source / 'stylist/main.py').write_text('# fixture ' + label)
    archive = tmp_path / (label + '.tar.gz')
    package(archive, root=source)
    # A fixture bootstrap is appended together with a replacement complete manifest.
    with tarfile.open(archive) as tar:
        tar.extractall(tmp_path / ('payload-' + label), filter='data')
    payload = tmp_path / ('payload-' + label) / 'aicloset-assistant'
    (payload / 'deploy/docker/runtime.defaults').write_text(
        'STYLIST_SERVER_URL=https://business.invalid\nSTYLIST_MCP_URL=https://business.invalid/mcp\n'
        'STYLIST_LLM_URL=https://model.invalid/v1\nSTYLIST_LLM_MODEL=fixture\nSTYLIST_LOGIN_APP_VERSION=1.2.0\n')
    (payload / 'deploy/docker/login-public.pem').write_text('fixture-public-key')
    if offline:
        # Fake Docker below verifies installer ordering, not image format or runtime compatibility.
        (payload / 'image.tar').write_bytes(b'synthetic-docker-image')
        (payload / 'image-name.txt').write_text('aicloset-stylist:offline-fixture\n')
    manifest = payload / 'MANIFEST.sha256'
    manifest.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(payload)) + '\n'
                                for p in sorted(payload.rglob('*')) if p.is_file() and p != manifest))
    with tarfile.open(archive, 'w:gz') as tar:
        tar.add(payload, arcname='aicloset-assistant')
    return archive


def run(archive, env):
    return subprocess.run(['bash', str(ROOT / 'install.sh'), str(archive)], env=env,
                          capture_output=True, text=True, timeout=30)


def test_install_then_update_preserves_config_and_switches_proxy_only_after_health(host):
    root, env = host
    first = run(make_release(root, 'first'), env)
    assert first.returncode == 0, first.stderr
    base = root / 'deployment'
    initial = (base / 'current').resolve()
    config = (base / 'config/deploy.env').read_bytes()
    assert b'STYLIST_LLM_KEY=synthetic-runtime$#key\n' in config
    assert (base / 'config/deploy.env').stat().st_mode & 0o777 == 0o600
    assert 'synthetic-runtime' not in first.stdout + first.stderr
    second = run(make_release(root, 'second'), {**env, 'STYLIST_LLM_KEY': 'must-not-overwrite-config'})
    assert second.returncode == 0, second.stderr
    assert (base / 'current').resolve() != initial and (base / 'previous').resolve() == initial
    assert (base / 'config/deploy.env').read_bytes() == config
    events = [json.loads(line) for line in (root / 'events').read_text().splitlines()]
    up = next(i for i, event in enumerate(events) if event[0] == 'docker' and 'up' in event[1])
    health = next(i for i, event in enumerate(events) if event[0] == 'curl')
    reload = next(i for i, event in enumerate(events) if event == ['nginx', ['-s', 'reload']])
    assert up < health < reload
    assert not any('down' in event[1] or 'volume' in event[1] for event in events)


def test_offline_release_loads_image_and_never_builds_or_pulls(host):
    root, env = host
    result = run(make_release(root, 'offline', offline=True), env)
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for line in (root / 'events').read_text().splitlines()]
    docker = [args for name, args in events if name == 'docker']
    assert any(args[:1] == ['load'] for args in docker)
    assert any(args[:2] == ['image', 'tag'] for args in docker)
    assert not any(args[:1] in (['build'], ['pull']) for args in docker)
    up = next(args for args in docker if args[:1] == ['compose'] and 'up' in args)
    assert up[up.index('--pull') + 1] == 'never' and '--no-build' in up


def test_first_install_reads_existing_private_config_without_key_prompt(host):
    root, env = host
    env.pop('STYLIST_LLM_KEY')
    config = root / 'deployment/config'
    config.mkdir(parents=True)
    original = b'STYLIST_LLM_KEY=synthetic-preseeded-only\n'
    (config / 'deploy.env').write_bytes(original)
    (config / 'deploy.env').chmod(0o600)
    (config / 'login-public.pem').write_text('fixture-public-key')
    result = run(make_release(root, 'preseeded', offline=True), env)
    assert result.returncode == 0, result.stderr
    assert '请输入' not in result.stdout + result.stderr
    assert 'synthetic-preseeded-only' not in result.stdout + result.stderr
    assert (config / 'deploy.env').read_bytes() == original


@pytest.mark.parametrize('failure', ['FAIL_BUILD', 'FAIL_UP', 'FAIL_NGINX', 'FAIL_PROXY'])
def test_failed_update_restores_previous_application_and_nginx(host, failure):
    root, env = host
    assert run(make_release(root, 'working'), env).returncode == 0
    base = root / 'deployment'
    previous = (base / 'current').resolve()
    old_image = (root / 'image').read_text()
    target = root / 'vhost/aicloset-assistant.wxbjq.top.conf'
    target.write_text('old site')
    result = run(make_release(root, 'broken'), {**env, failure: '1'})
    assert result.returncode != 0
    assert (base / 'current').resolve() == previous
    assert (root / 'image').read_text() == old_image
    assert target.read_text() == 'old site'
    assert (root / 'running').exists()


def test_unrelated_port_listener_is_not_stopped(host):
    root, env = host
    result = run(make_release(root, 'blocked'), {**env, 'FAIL_PORT': '1'})
    assert result.returncode != 0 and '8466' in result.stderr
    events = [json.loads(line) for line in (root / 'events').read_text().splitlines()]
    assert not any('up' in event[1] or 'stop' in event[1] for event in events)


def test_documented_extract_and_run_pipeline_works(host):
    root, env = host
    archive = make_release(root, 'pipeline')
    result = subprocess.run(['bash', '-o', 'pipefail', '-c',
        'tar -xOf "$1" aicloset-assistant/install.sh | bash -s -- "$1"', 'deploy', str(archive)],
        env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert (root / 'deployment/current').is_symlink()


def test_first_install_can_read_key_privately_from_terminal_while_script_is_piped(host):
    root, env = host
    env.pop('STYLIST_LLM_KEY')
    archive = make_release(root, 'terminal')
    secret = b'synthetic-terminal-only-key'
    pid, fd = pty.fork()
    if pid == 0:
        os.execvpe('bash', ['bash', '-o', 'pipefail', '-c',
            'tar -xOf "$1" aicloset-assistant/install.sh | bash -s -- "$1"', 'deploy', str(archive)], env)
    output = b''
    submitted = False
    deadline = time.monotonic() + 25
    try:
        while time.monotonic() < deadline:
            if select.select([fd], [], [], .2)[0]:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
                if not submitted and '输入不回显'.encode() in output:
                    time.sleep(.05)
                    os.write(fd, secret + b'\n')
                    submitted = True
        else:
            os.kill(pid, 9)
            pytest.fail('Installer terminal prompt timed out')
    finally:
        os.close(fd)
        _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0, output.decode(errors='replace')
    assert submitted and secret not in output
    assert secret in (root / 'deployment/config/deploy.env').read_bytes()


def test_existing_domain_in_another_site_is_not_overwritten(host):
    root, env = host
    other = root / 'vhost/other-site.conf'
    original = 'server { server_name other.example; }\nserver_name aicloset-assistant.wxbjq.top;\n'
    other.write_text(original)
    result = run(make_release(root, 'duplicate'), env)
    assert result.returncode != 0 and '域名' in result.stderr
    assert other.read_text() == original
    assert not (root / 'running').exists()


@pytest.mark.parametrize('kind', ['traversal', 'symlink'])
def test_unsafe_archive_cannot_escape_release_directory(host, kind):
    root, env = host
    archive = root / 'unsafe.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        member = tarfile.TarInfo('aicloset-assistant/../../escape' if kind == 'traversal' else 'aicloset-assistant/link')
        if kind == 'symlink':
            member.type, member.linkname = tarfile.SYMTYPE, '/etc'
        tar.addfile(member)
    result = run(archive, env)
    assert result.returncode != 0
    assert not (root / 'escape').exists() and not (root / 'running').exists()
