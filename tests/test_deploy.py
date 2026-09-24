"""Offline integration tests: actual Git repositories; no real SSH/Docker/GitHub."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REAL_GIT = shutil.which('git')
PYTHON = shutil.which('python3')

class DeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='deploy-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'local'
        self.remote = self.base / 'server'
        self.checkout = self.remote / 'repository'
        self.data = self.base / 'data'
        self.envfile = self.remote / 'shared' / '.env'
        self.bin = self.base / 'bin'
        for folder in (self.repo, self.remote, self.data, self.envfile.parent, self.bin):
            folder.mkdir(parents=True, exist_ok=True)
        self.envfile.write_text('DATABASE_URL=super-secret-database-value\n')
        self.env = dict(os.environ)
        for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GH_REPO'):
            self.env.pop(key, None)
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                        GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                        GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid',
                        TEST_BASE=str(self.base), TEST_REAL_GIT=REAL_GIT,
                        PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        self.git('init', '-q', '-b', 'main', str(self.repo))
        (self.repo / '.deploy').mkdir()
        self.manifest = {
            'version': 1, 'application': {'name': 'myapp'},
            'server': {'deploy_path': str(self.remote)},
            'docker': {'compose_file': 'compose.yaml', 'image': 'myapp'},
            'environment': {'file': str(self.envfile), 'required': ['DATABASE_URL']},
            'directories': {'required': [str(self.data)]},
            'verify': {'services': ['app'], 'directories': [str(self.data)],
                       'health': {'url': 'http://127.0.0.1:3000/health', 'status': 200}}}
        self.manifest_path = self.repo / '.deploy' / 'manifest.yaml'
        self.manifest_path.write_text(json.dumps(self.manifest))  # JSON is YAML.
        (self.repo / 'compose.yaml').write_text('services:\n  app:\n    image: myapp:${APP_VERSION}\n    build: .\n')
        self.commit_release()
        self.git('clone', '-q', str(self.repo), str(self.checkout), cwd=self.base)
        self.git('remote', 'add', 'origin', 'https://github.com/example/app.git')
        self.git('remote', 'set-url', 'origin', 'https://github.com/example/app.git', cwd=self.checkout)
        self.write_stub('git', '''
args = sys.argv[1:]
remote = os.environ.get('TEST_REMOTE') == '1'
if remote and os.environ.get('CASE') == 'remote_git_missing': sys.exit(127)
if args[:2] == ['fetch', 'origin']:
    args[1] = os.environ['TEST_BASE'] + '/local'
args = [os.environ['TEST_BASE'] + '/local' if a.startswith('https://github.com/example/app') else a for a in args]
if remote and args[:1] == ['rev-parse'] and 'refs/tags/' in ' '.join(args) and os.environ.get('CASE') == 'mismatch':
    print('a' * 40); sys.exit(0)
if remote and args[:1] in (['fetch'], ['checkout']): log('git ' + ' '.join(args))
sys.exit(subprocess.call([os.environ['TEST_REAL_GIT']] + args))
''')
        self.write_stub('gh', '''
args = sys.argv[1:]
if args[:2] == ['auth', 'status']: sys.exit(1 if os.environ.get('CASE') == 'auth' else 0)
if args[:1] == ['api']:
    if os.environ.get('CASE') == 'tag_missing': sys.exit(1)
    sha = subprocess.check_output([os.environ['TEST_REAL_GIT'], '-C', os.environ['TEST_BASE'] + '/local', 'rev-parse', 'v1.0.0^{commit}'], text=True).strip()
    if os.environ.get('CASE') == 'github_mismatch': sha = 'b' * 40
    if os.environ.get('CASE') == 'annotated' and '/git/ref/' in args[-1]:
        print(json.dumps({'object': {'type': 'tag', 'sha': 'c' * 40}})); sys.exit(0)
    print(json.dumps({'object': {'type': 'commit', 'sha': sha}})); sys.exit(0)
if args[:2] == ['release', 'view']:
    if os.environ.get('CASE') == 'release_missing': sys.exit(1)
    print(json.dumps({'tagName': 'v1.0.0', 'isDraft': os.environ.get('CASE') == 'draft', 'publishedAt': '2026-01-01T00:00:00Z'})); sys.exit(0)
sys.exit(99)
''')
        self.write_stub('ssh', '''
log('ssh ' + ' '.join(sys.argv[1:]))
if os.environ.get('CASE') == 'ssh': sys.exit(255)
if os.environ.get('CASE') == 'remote_python_missing': sys.exit(127)
env = dict(os.environ, TEST_REMOTE='1')
if os.environ.get('CASE') == 'disk':
    source = 'import shutil; shutil.disk_usage = lambda path: type(\"Disk\", (), {\"free\": 0})()\\n' + sys.stdin.read()
    sys.exit(subprocess.run([sys.executable, '-'], env=env, input=source, text=True).returncode)
sys.exit(subprocess.call([sys.executable, '-'], env=env))
''')
        self.write_stub('docker', '''
args = sys.argv[1:]
case = os.environ.get('CASE')
if case == 'remote_docker_missing': sys.exit(127)
if args == ['--version']: print('Docker test'); sys.exit(0)
if args[:2] == ['info', '--format']: print('/nonexistent-docker-root' if case == 'docker_root' else os.environ['TEST_BASE']); sys.exit(0)
if args == ['info']: sys.exit(1 if case == 'daemon' else 0)
if args[:2] == ['context', 'inspect']: print('ssh://other-host' if case == 'docker_context' else 'unix:///var/run/docker.sock'); sys.exit(0)
if args == ['compose', 'version']: sys.exit(1 if case == 'compose_missing' else 0)
if os.environ.get('APP_VERSION') != 'v1.0.0': sys.exit(98)
log('docker ' + ' '.join(args))
if 'config' in args:
    image = 'myapp:latest' if case == 'wrong_image' else 'myapp:v1.0.0'
    service = {'image': image, 'build': {'context': '.'}}
    if case == 'extra_environment':
        service['environment'] = {'EXTRA': 'service-env-file-value'}
        service['build']['args'] = {'TOKEN': 'build-arg-value'}
    if case in ('bind_missing', 'bind_create'):
        source = os.environ['TEST_BASE'] + ('/missing-data' if case == 'bind_missing' else '/data')
        service['volumes'] = [{'type': 'bind', 'source': source, 'target': '/data', 'bind': {'create_host_path': True}}]
    print(json.dumps({'services': {'app': service}})); sys.exit(0)
if 'build' in args:
    if case == 'url_password': print('password db-password-fragment', flush=True)
    elif case == 'extra_environment': print('extra env inherited-token-value service-env-file-value build-arg-value', flush=True)
    else:
        value = open(os.environ['TEST_BASE'] + '/server/shared/.env').read()
        print('building ' + ('super-secret-database-value' if 'super-secret-database-value' in value else 'image'), flush=True)
    sys.exit(1 if case == 'build' else 0)
if 'up' in args: sys.exit(1 if case == 'start' else 0)
if 'ps' in args:
    if '--services' in args: print('other' if case == 'containers' else 'app')
    else: print('app running')
    sys.exit(0)
sys.exit(99)
''')
        self.write_stub('curl', '''
if sys.argv[1:] == ['--version']: print('curl test'); sys.exit(0)
log('curl')
print('503' if os.environ.get('CASE') == 'health' else '200', end='')
''')

    def write_stub(self, name, body):
        text = '#!' + PYTHON + '\nimport os,sys,json,subprocess\n'
        text += 'def log(s):\n    with open(os.environ["TEST_BASE"] + "/calls", "a") as f: f.write(s + "\\n")\n'
        (self.bin / name).write_text(text + body)
        (self.bin / name).chmod(0o755)

    def git(self, *args, cwd=None):
        return subprocess.check_output([REAL_GIT, *args], cwd=cwd or self.repo, env=self.env, stderr=subprocess.DEVNULL, text=True).strip()

    def commit_release(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture', '--allow-empty')
        self.git('tag', '-fa', 'v1.0.0', '-m', 'release')
        self.sha = self.git('rev-parse', 'HEAD')

    def run_deploy(self, *args, case='', verify=False):
        env = dict(self.env, CASE=case)
        result = subprocess.run(['bash', str(ROOT / 'scripts' / ('verify-deployment.sh' if verify else 'deploy.sh')), *args],
                                cwd=self.repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        self.output = result.stdout
        self.calls = (self.base / 'calls').read_text() if (self.base / 'calls').exists() else ''
        self.assertNotIn('super-secret-database-value', self.output)
        return result

    def failure(self, phrase, case='', args=('v1.0.0', 'test-host'), no_ssh=False, no_build=True):
        result = self.run_deploy(*args, case=case)
        self.assertNotEqual(result.returncode, 0, self.output)
        self.assertIn(phrase, self.output)
        self.assertNotIn('AWAITING MANUAL VERIFICATION', self.output)
        if no_ssh: self.assertNotIn('ssh ', self.calls)
        if no_build: self.assertNotIn(' build', self.calls)
        if 'DEPLOYMENT BLOCKED' in self.output:
            self.assertNotIn('git fetch', self.calls)
            self.assertNotIn('git checkout', self.calls)

    def test_missing_version(self): self.failure('Usage:', args=(), no_ssh=True)
    def test_missing_server(self): self.failure('Usage:', args=('v1.0.0',), no_ssh=True)
    def test_release_missing(self): self.failure('Release', case='release_missing', no_ssh=True)
    def test_draft(self): self.failure('Draft', case='draft', no_ssh=True)
    def test_auth(self): self.failure('authentication', case='auth', no_ssh=True)
    def test_manifest_missing(self):
        self.manifest_path.unlink(); self.commit_release()
        self.failure('manifest', no_ssh=True)
    def test_manifest_invalid(self):
        self.manifest_path.write_text('version: [broken'); self.commit_release()
        self.failure('manifest', no_ssh=True)
    def test_manifest_missing_field(self):
        del self.manifest['environment']; self.manifest_path.write_text(json.dumps(self.manifest)); self.commit_release()
        self.failure('manifest', no_ssh=True)
    def test_ssh_failure(self): self.failure('DEPLOYMENT BLOCKED', case='ssh')
    def test_remote_git_missing(self): self.failure('git', case='remote_git_missing')
    def test_remote_docker_missing(self): self.failure('docker', case='remote_docker_missing')
    def test_remote_compose_missing(self): self.failure('compose', case='compose_missing')
    def test_daemon_failure(self): self.failure('daemon', case='daemon')
    def test_env_file_missing(self):
        self.envfile.unlink(); self.failure('environment file')
    def test_required_env_missing(self):
        self.envfile.write_text('OTHER=abc\n'); self.failure('DATABASE_URL')
    def test_required_directory_missing(self):
        self.data.rmdir(); self.failure('directory')
    def test_tag_mismatch(self): self.failure('commit mismatch', case='mismatch')
    def test_build_failure(self):
        self.failure('DEPLOYMENT FAILED', case='build', no_build=False)
        self.assertNotIn(' up -d', self.calls)
    def test_start_failure(self): self.failure('DEPLOYMENT FAILED', case='start', no_build=False)
    def test_health_failure(self): self.failure('Health Check', case='health', no_build=False)
    def test_containers_failure(self): self.failure('Containers', case='containers', no_build=False)
    def test_wrong_image(self): self.failure('image', case='wrong_image')
    def test_dirty_remote(self):
        (self.checkout / 'dirty').write_text('change'); self.failure('working tree')
    def test_working_manifest_ignored(self):
        self.manifest_path.write_text('invalid local manifest')
        result = self.run_deploy('v1.0.0', 'test-host')
        self.assertEqual(result.returncode, 0, self.output)
        self.assertIn('5 / 5 PASSED', self.output)
        self.assertIn('AWAITING MANUAL VERIFICATION', self.output)
        self.assertIn(self.sha, self.output)
        self.assertLess(self.output.index('Deployment Plan'), self.output.index('SSH connectivity'))
        self.assertIn('[REDACTED]', self.output)
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.checkout), self.sha)
        self.assertEqual(self.envfile.read_text(), 'DATABASE_URL=super-secret-database-value\n')
        self.assertIn('BatchMode=yes', self.calls)
        self.assertNotIn('git pull', self.calls)
    def test_invalid_server(self): self.failure('Invalid SSH', args=('v1.0.0', '-oProxyCommand=bad'), no_ssh=True)
    def test_invalid_version(self): self.failure('Invalid release', args=('--bad', 'test-host'), no_ssh=True)
    def test_tag_missing(self): self.failure('Tag', case='tag_missing', no_ssh=True)
    def test_github_commit_mismatch(self): self.failure('commit mismatch', case='github_mismatch', no_ssh=True)
    def test_annotated_github_tag(self):
        result = self.run_deploy('v1.0.0', 'test-host', case='annotated')
        self.assertEqual(result.returncode, 0, self.output)
    def test_manifest_duplicate_key(self):
        self.manifest_path.write_text('version: 1\nversion: 1\n'); self.commit_release()
        self.failure('manifest', no_ssh=True)
    def test_manifest_old_schema(self):
        self.manifest['version'] = 'v1.0.0'
        self.manifest_path.write_text(json.dumps(self.manifest)); self.commit_release()
        self.failure('manifest', no_ssh=True)
    def test_manifest_compose_escape(self):
        self.manifest['docker']['compose_file'] = '../outside.yaml'
        self.manifest_path.write_text(json.dumps(self.manifest)); self.commit_release()
        self.failure('manifest', no_ssh=True)
    def test_manifest_health_credentials(self):
        self.manifest['verify']['health']['url'] = 'http://user:password@localhost/health'
        self.manifest_path.write_text(json.dumps(self.manifest)); self.commit_release()
        self.failure('manifest', no_ssh=True)
        self.assertNotIn('password', self.output)
    def test_environment_not_executed(self):
        marker = self.base / 'executed'
        self.envfile.write_text("DATABASE_URL='$(touch " + str(marker) + ")'\nOTHER=super-secret-database-value\n")
        result = self.run_deploy('v1.0.0', 'test-host')
        self.assertEqual(result.returncode, 0, self.output)
        self.assertFalse(marker.exists())
    def test_environment_reserved_variable(self):
        self.envfile.write_text('DATABASE_URL=abc\nDOCKER_HOST=tcp://evil\n')
        self.failure('reserved runtime')
    def test_empty_required_environment(self):
        self.envfile.write_text('DATABASE_URL=\n'); self.failure('DATABASE_URL')
    def test_environment_in_repository(self):
        self.manifest['environment']['file'] = str(self.checkout / '.env')
        self.manifest_path.write_text(json.dumps(self.manifest)); self.commit_release()
        self.failure('outside repository')
    def test_remote_wrong_origin(self):
        self.git('remote', 'set-url', 'origin', 'https://github.com/other/project.git', cwd=self.checkout)
        self.failure('origin repository mismatch')
    def test_docker_data_directory_inaccessible(self): self.failure('disk path', case='docker_root')
    def test_verify_commit_mismatch(self):
        self.git('commit', '--allow-empty', '-qm', 'other', cwd=self.checkout)
        result = self.run_deploy('v1.0.0', 'test-host', verify=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Git Commit: FAIL', self.output)
        self.assertNotIn(' build', self.calls)

    def test_url_password_fragment_redacted(self):
        self.envfile.write_text('DATABASE_URL=postgres://user:db-password-fragment@localhost/db\n')
        result = self.run_deploy('v1.0.0', 'test-host', case='url_password')
        self.assertEqual(result.returncode, 0, self.output)
        self.assertNotIn('db-password-fragment', self.output)
        self.assertIn('[REDACTED]', self.output)
    def test_bind_source_missing(self): self.failure('bind source', case='bind_missing')
    def test_bind_cannot_create_directory(self): self.failure('create_host_path', case='bind_create')
    def test_remote_docker_context(self): self.failure('Unix socket', case='docker_context')

    def test_extra_environment_values_redacted(self):
        self.env['EXTRA_TOKEN'] = 'inherited-token-value'
        result = self.run_deploy('v1.0.0', 'test-host', case='extra_environment')
        self.assertEqual(result.returncode, 0, self.output)
        for secret in ('inherited-token-value', 'service-env-file-value', 'build-arg-value'):
            self.assertNotIn(secret, self.output)
    def test_stateless_manifest(self):
        self.manifest['environment']['required'] = []
        self.manifest['directories']['required'] = []
        self.manifest['verify']['directories'] = []
        self.manifest_path.write_text(json.dumps(self.manifest)); self.commit_release()
        # Remote stale tag is intentionally synchronized for this successful case.
        self.git('tag', '-d', 'v1.0.0', cwd=self.checkout)
        result = self.run_deploy('v1.0.0', 'test-host')
        self.assertEqual(result.returncode, 0, self.output)

    def test_remote_python_missing(self): self.failure('DEPLOYMENT BLOCKED', case='remote_python_missing')
    def test_insufficient_disk(self): self.failure('Insufficient disk', case='disk')

    def test_checkout_exact_commit_from_newer_remote_head(self):
        self.git('commit', '--allow-empty', '-qm', 'server ahead', cwd=self.checkout)
        result = self.run_deploy('v1.0.0', 'test-host')
        self.assertEqual(result.returncode, 0, self.output)
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.checkout), self.sha)
        detached = subprocess.run([REAL_GIT, 'symbolic-ref', '-q', 'HEAD'], cwd=self.checkout,
                                  env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertNotEqual(detached.returncode, 0)

    def test_verify_only(self):
        result = self.run_deploy('v1.0.0', 'test-host', verify=True)
        self.assertEqual(result.returncode, 0, self.output)
        self.assertNotIn('git fetch', self.calls)
        self.assertNotIn('git checkout', self.calls)
        self.assertNotIn(' build', self.calls)
        self.assertNotIn(' up -d', self.calls)


class DependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('deployment', ROOT / 'scripts/deployment.py')
        cls.deployment = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.deployment)

    def missing(self, tool):
        with mock.patch.object(self.deployment.shutil, 'which', side_effect=lambda name: None if name == tool else '/stub/' + name):
            with self.assertRaisesRegex(self.deployment.DeploymentError, tool + ' is required'):
                self.deployment.local_config('deploy', 'v1.0.0', 'test-host')

    def test_local_git_missing(self): self.missing('git')
    def test_local_gh_missing(self): self.missing('gh')
    def test_local_ssh_missing(self): self.missing('ssh')
    def test_pyyaml_missing(self):
        with mock.patch.object(self.deployment.shutil, 'which', return_value='/stub/tool'):
            with mock.patch.dict('sys.modules', {'yaml': None}):
                with self.assertRaisesRegex(self.deployment.DeploymentError, 'PyYAML'):
                    self.deployment.local_config('deploy', 'v1.0.0', 'test-host')

if __name__ == '__main__':
    unittest.main(verbosity=2)
