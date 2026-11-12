import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import uuid

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_ci_uses_server_compatible_basic_keywords_and_server_deployment_lock():
    ci=yaml.safe_load((ROOT/'.gitlab-ci.yml').read_text())
    assert ci['variables']['DEPLOY_ENV']=='dev'
    assert ci['variables']['DEPLOY_HOST']=='172.16.0.90'
    assert set(ci)=={'variables','stages','job_build','job_deploy'}
    for name in ['job_build','job_deploy']:
        job=ci[name]
        assert set(job)=={'stage','script','tags','only'}
        assert job['tags']==['devops-test']
        assert job['only']==['main','web']
        assert all(isinstance(command,str) for command in job['script'])
    assert 'flock -w 600' in (ROOT/'deploy/ci/deploy.sh').read_text()
    script='\n'.join(ci['job_deploy']['script'])
    assert 'STYLIST_TEST_ENV_FILE' not in script and 'STYLIST_DEV_ENV_FILE' not in script
    assert 'deploy-aicloset-agent.sh' not in script
    assert '< deploy/ci/deploy.sh' in script


def test_ci_archive_never_includes_private_config_or_user_evidence(tmp_path):
    root=tmp_path/'repo';(root/'scripts').mkdir(parents=True)
    shutil.copy(ROOT/'scripts/ci_package.sh',root/'scripts/ci_package.sh')
    for name in ['Dockerfile','.dockerignore','pyproject.toml','uv.lock','README.md','stylist/main.py','deploy/docker/start.sh','deploy/ci/deploy.sh','deploy/ci/Dockerfile.offline',
                 'stylist/static/remote-image.png','config/deploy.env','var/user-data.json','reports/private.html','stylist/static/closet-app/comparison/evolution/screenshots/private/user.png']:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic')
    (root/'.dockerignore').write_text('# BEGIN OSS image exclusions (generated)\nstylist/static/remote-image.png\n# END OSS image exclusions\n')
    result=subprocess.run(['bash',str(root/'scripts/ci_package.sh'),'test','123','a'*40],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    archive=next((root/'var/ci-release').glob('*.tar.gz'))
    with tarfile.open(archive) as t:
        names=t.getnames()
    assert 'stylist/main.py' in names and 'deploy/ci/deploy.sh' in names
    assert 'stylist/static/remote-image.png' not in names
    assert not any(n.startswith(('config/','var/','reports/')) or '/private/' in n for n in names)
    assert archive.with_name(archive.name+'.sha256').read_text().split()[0]==hashlib.sha256(archive.read_bytes()).hexdigest()


@pytest.mark.parametrize('environment',['prod','test;touch /tmp/invalid'])
def test_unknown_environment_is_rejected_without_running_docker(environment,tmp_path):
    r=subprocess.run(['bash',str(ROOT/'deploy/ci/deploy.sh'),environment,'x','a'*40,str(tmp_path)],capture_output=True,text=True)
    assert r.returncode!=0 and 'DEPLOY_ENV must be test or dev' in r.stderr


@pytest.mark.parametrize('mode,successful',[('ok',True),('candidate-fail',False),('public-fail',False),('config-fail',False)])
def test_deploy_switches_only_after_candidate_and_restores_old_on_failure(tmp_path,mode,successful):
    bindir=tmp_path/'bin';bindir.mkdir();log=tmp_path/'calls.log'
    docker='''#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
with open(os.environ['CALL_LOG'],'a') as f:f.write('docker '+' '.join(args)+'\\n')
mode=os.environ['TEST_MODE']
if args[0]=='ps' and '-q' in args: print('old-id')
if args[0]=='inspect': print('/recommend-outfit')
if args[0]=='exec' and mode=='candidate-fail':sys.exit(1)
if args[0]=='run' and '--rm' in args and '--entrypoint' in args and mode=='config-fail':sys.exit(1)
'''
    curl='''#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
if os.environ['TEST_MODE']=='public-fail' and args[-1].endswith('/ops/conversations'):sys.exit(22)
if '%{http_code}' in args:print('401',end='')
elif args[-1].endswith('/health'):print('{"revision":"'+'b'*40+'"}')
else:print('{"ready":true}')
'''
    for name,content in {'docker':docker,'curl':curl,'id':'#!/bin/sh\necho 0\n','flock':'#!/bin/sh\nexit 0\n','sleep':'#!/bin/sh\nexit 0\n','ss':'#!/bin/sh\nexit 0\n'}.items():
        p=bindir/name;p.write_text(content);p.chmod(0o755)
    root=tmp_path/'deploy';(root/'config').mkdir(parents=True)
    (root/'config/test.env').write_text('FIXTURE=private-value\nLANGFUSE_SECRET_KEY=retired-secret\nLANGFUSE_TRACING_ENABLED=true\n')
    (root/'config/login-public.pem').write_text('synthetic-public-key')
    commit='b'*40;archive=Path('/tmp')/f'aicloset-agent-test-{uuid.uuid4().int}-{commit}.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        for name,data in [('Dockerfile',b'FROM scratch\n'),('uv.lock',b'synthetic lock\n')]:
            info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
    checksum=archive.with_name(archive.name+'.sha256');checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    try:
        env={**os.environ,'PATH':str(bindir)+os.pathsep+os.environ['PATH'],'CALL_LOG':str(log),'TEST_MODE':mode}
        r=subprocess.run(['bash',str(ROOT/'deploy/ci/deploy.sh'),'test',str(archive),commit,str(root)],env=env,capture_output=True,text=True)
        assert (r.returncode==0)==successful,r.stdout+r.stderr
        calls=log.read_text()
        assert 'private-value' not in r.stdout+r.stderr+calls
        if successful:
            assert 'docker stop -t 330 old-id' in calls
            assert (root/'current-test').is_symlink()
            assert 'LANGFUSE_' not in (root/'config/test.env').read_text()
            assert '-e LANGFUSE_TRACING_ENABLED=false' in calls
        elif mode in {'candidate-fail','config-fail'}:
            assert 'docker stop' not in calls
        else:
            assert 'docker start old-id' in calls
            assert not (root/'current-test').exists()
    finally:archive.unlink(missing_ok=True);checksum.unlink(missing_ok=True)


def test_health_reports_only_valid_explicit_build_revision(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from stylist.main import create_app
    from stylist.config import Settings
    monkeypatch.setenv('STYLIST_BUILD_COMMIT','a'*40)
    with TestClient(create_app(Settings(database=str(tmp_path/'health.db')))) as client:
        assert client.get('/health').json()['revision']=='a'*40
        monkeypatch.setenv('STYLIST_BUILD_COMMIT','invalid-private-input')
        assert 'revision' not in client.get('/health').json()


def test_ci_templates_do_not_require_tracing_credentials():
    for name in ['test','dev']:
        text=(ROOT/f'deploy/{name}.env.example').read_text()
        assert 'LANGFUSE_' not in text
    script=(ROOT/'deploy/ci/deploy.sh').read_text()
    assert 'Incorrect Langfuse project environment' not in script
    assert 'LANGFUSE_TRACING_ENABLED=false' in script


def test_dependency_layer_precedes_application_sources():
    text=(ROOT/'Dockerfile').read_text()
    assert text.index('uv sync --frozen --no-dev --no-install-project') < text.index('COPY stylist')
    assert text.index('COPY stylist') < text.rindex('RUN uv sync --frozen --no-dev')


@pytest.mark.parametrize('environment',['dev','test'])
def test_full_environment_guard_rejects_crossed_database_server_mcp_and_callback(environment):
    from dataclasses import replace
    from stylist.config import Settings
    from stylist.deploy_config import validate,DATABASES
    other='dev' if environment=='test' else 'test'
    server=f'https://aicloset-{environment}.wxbjq.top'
    settings=Settings(server_url=server,mcp_url=server+'/mcp',
        usage_callback_url=server+'/api/internal/stylist/model-usage',usage_environment='test',
        database='postgresql://fixture:private-secret@db.invalid/'+DATABASES[environment],
        llm_url='https://model.invalid',llm_model='fixture',llm_key='synthetic',ops_mysql_dsn='synthetic')
    validate(settings,environment)
    cases={
        'database':'postgresql://fixture:private-secret@db.invalid/'+DATABASES[other],
        'checkpoint_database':'postgresql://fixture:private-secret@db.invalid/'+DATABASES[other],
        'server_url':f'https://aicloset-{other}.wxbjq.top',
        'mcp_url':f'https://aicloset-{other}.wxbjq.top/mcp',
        'usage_callback_url':f'https://aicloset-{other}.wxbjq.top/api/internal/stylist/model-usage',
        'usage_environment':'prod',
    }
    for field,value in cases.items():
        with pytest.raises(ValueError) as error:validate(replace(settings,**{field:value}),environment)
        assert 'private-secret' not in str(error.value)


def test_sql_baseline_is_not_ignored_but_editor_swaps_are():
    baseline='stylist/migrations/postgresql/001_initial.sql'
    result=subprocess.run(['git','check-ignore','--no-index',baseline],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==1, result.stdout
    for name in ['.gitlab-ci.yml.swp','.gitlab-ci.yml.swo','.gitlab-ci.yml.swn']:
        result=subprocess.run(['git','check-ignore','--no-index',name],cwd=ROOT,capture_output=True,text=True)
        assert result.returncode==0,name


def test_ci_build_uses_loaded_runtime_and_disables_network():
    deploy=(ROOT/'deploy/ci/deploy.sh').read_text()
    dockerfile=(ROOT/'deploy/ci/Dockerfile.offline').read_text()
    assert 'docker image inspect "$runtime_image"' in deploy
    assert 'docker build --pull=false --network none' in deploy
    assert 'STYLIST_RUNTIME_IMAGE=$runtime_image' in deploy
    assert 'sha256sum "$release/source/uv.lock"' in deploy
    assert 'uv sync' not in dockerfile and 'pip install' not in dockerfile
    assert 'RUN rm -rf /app/stylist' in dockerfile
    assert 'deploy/ci/Dockerfile.offline' in (ROOT/'scripts/ci_package.sh').read_text()


def test_ops_mysql_templates_use_separate_environment_databases():
    for environment in ['dev','test']:
        text=(ROOT/f'deploy/{environment}.env.example').read_text()
        dsn=next(line for line in text.splitlines() if line.startswith('STYLIST_OPS_MYSQL_DSN='))
        assert dsn.endswith('/aicloset_'+environment)
