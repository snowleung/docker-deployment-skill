"""Deploy V1 implementation. Only parse_manifest imports PyYAML (local side)."""
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qsl, quote, quote_plus, unquote, urlsplit

MIN_FREE_BYTES = 1024 ** 3


class DeploymentError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise DeploymentError(message)


def capture(args, message, cwd=None, env=None):
    # Raw diagnostics may contain credentials, URLs or expanded configuration.
    try:
        result = subprocess.run(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding='utf-8', errors='replace')
    except OSError:
        raise DeploymentError(message) from None
    require(result.returncode == 0, message)
    return result.stdout.strip()


def github_repo(url):
    # Explicitly scope gh calls to origin; ignore gh's default repo/GH_REPO.
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?', url)
    require(match is not None, 'origin must be a credential-free github.com HTTPS or SSH repository URL.')
    return match.group(1)


def parse_manifest(text):
    try:
        import yaml
    except ImportError:
        raise DeploymentError('PyYAML is required locally; see README dependencies.') from None

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node):
        values = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            if not isinstance(key, str) or key in values:
                raise ValueError('duplicate or nonstring key')
            values[key] = loader.construct_object(value_node, deep=True)
        return values

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        manifest = yaml.load(text, Loader=UniqueLoader)
    except (yaml.YAMLError, ValueError, TypeError, RecursionError):
        raise DeploymentError('Invalid manifest YAML (duplicate keys and custom tags are not supported).') from None

    def fields(obj, names, where):
        require(type(obj) is dict and set(obj) == set(names.split()), 'Invalid manifest fields: ' + where)

    def string(value, where):
        require(isinstance(value, str) and bool(value) and all(32 <= ord(c) < 127 for c in value),
                'Invalid manifest string: ' + where)
        return value

    def absolute(value, where):
        string(value, where)
        require(value.startswith('/') and value != '/' and '..' not in PurePosixPath(value).parts,
                'Invalid manifest absolute path: ' + where)

    def sequence(value, where):
        require(isinstance(value, list) and all(isinstance(v, str) for v in value)
                and len(set(value)) == len(value), 'Invalid manifest list: ' + where)

    fields(manifest, 'version application server docker environment directories verify', 'root')
    require(type(manifest['version']) is int and manifest['version'] == 1, 'Invalid manifest version: expected schema version 1.')
    for name, keys in [('application', 'name'), ('server', 'deploy_path'), ('docker', 'compose_file image'),
                       ('environment', 'file required'), ('directories', 'required'), ('verify', 'services directories health')]:
        fields(manifest[name], keys, name)
    fields(manifest['verify']['health'], 'url status', 'verify.health')
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]*', string(manifest['application']['name'], 'application.name')),
            'Invalid manifest application.name.')
    absolute(manifest['server']['deploy_path'], 'server.deploy_path')
    absolute(manifest['environment']['file'], 'environment.file')
    compose = string(manifest['docker']['compose_file'], 'docker.compose_file')
    require(not compose.startswith('/') and '..' not in PurePosixPath(compose).parts and compose != '.',
            'Invalid manifest docker.compose_file: use a repository-relative path without ..')
    require(re.fullmatch(r'[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*',
                        string(manifest['docker']['image'], 'docker.image')),
            'Invalid manifest docker.image: use an image name without tag, digest or registry port.')
    for section, key in [('environment', 'required'), ('directories', 'required'), ('verify', 'services'), ('verify', 'directories')]:
        sequence(manifest[section][key], section + '.' + key)
    require(manifest['verify']['services'], 'Invalid manifest verify.services: at least one service is required.')
    for name in manifest['environment']['required']:
        require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name), 'Invalid manifest environment variable name.')
    for name in manifest['verify']['services']:
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name), 'Invalid manifest service name.')
    for path in manifest['directories']['required'] + manifest['verify']['directories']:
        absolute(path, 'directories')
    health = manifest['verify']['health']
    try:
        url = urlsplit(string(health['url'], 'verify.health.url'))
        _ = url.port
    except ValueError:
        raise DeploymentError('Invalid manifest health URL.') from None
    require(url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password
            and not url.query and not url.fragment, 'Invalid manifest health URL: HTTP(S), no credentials/query/fragment.')
    require(type(health['status']) is int and 100 <= health['status'] <= 599, 'Invalid manifest health status.')
    return manifest


def local_config(mode, version, server):
    require(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', version) and version != 'latest',
            'Invalid release version: must also be a Docker image tag, not latest.')
    require(re.fullmatch(r'(?:[A-Za-z0-9_][A-Za-z0-9_.-]*@)?[A-Za-z0-9][A-Za-z0-9_.-]*', server),
            'Invalid SSH server: use user@hostname or an SSH config alias.')
    require(sys.version_info >= (3, 9), 'Python 3.9+ is required locally.')
    for tool in ('git', 'gh', 'ssh'):
        require(shutil.which(tool), tool + ' is required.')
    try:
        import yaml  # noqa: F401 -- dependency checked before external operations
    except ImportError:
        raise DeploymentError('PyYAML is required locally; see README dependencies.') from None
    capture(['gh', 'auth', 'status', '--hostname', 'github.com'], 'GitHub authentication failed.')
    require(capture(['git', 'rev-parse', '--is-inside-work-tree'], 'Run from a Git repository.') == 'true', 'Run from a Git repository.')
    origin = capture(['git', 'remote', 'get-url', 'origin'], 'Cannot read origin repository.')
    repo = github_repo(origin)
    try:
        release = json.loads(capture(['gh', 'release', 'view', version, '--repo', 'github.com/' + repo, '--json', 'tagName,isDraft,publishedAt'],
                                     'GitHub Release does not exist or cannot be read.'))
        require(release.get('isDraft') is False and release.get('publishedAt'), 'Draft or unpublished Release cannot be deployed.')
        tag = release.get('tagName')
        require(tag == version, 'Release Tag must match requested version.')
        ref = json.loads(capture(['gh', 'api', '--hostname', 'github.com', 'repos/' + repo + '/git/ref/tags/' + quote(tag, safe='')],
                                 'Release Tag does not exist on GitHub.'))['object']
        for _ in range(16):
            require(re.fullmatch(r'[0-9a-f]{40}', ref['sha']), 'Invalid GitHub object SHA.')
            if ref['type'] == 'commit':
                break
            require(ref['type'] == 'tag', 'Release Tag does not resolve to a commit.')
            ref = json.loads(capture(['gh', 'api', '--hostname', 'github.com', 'repos/' + repo + '/git/tags/' + ref['sha']],
                                     'Cannot resolve annotated GitHub Tag.'))['object']
        require(ref['type'] == 'commit', 'Release Tag nesting limit exceeded.')
        commit = ref['sha']
    except (ValueError, TypeError, KeyError, AttributeError):
        raise DeploymentError('Invalid GitHub Release/Tag response.') from None
    # Isolate fetched refs from the user's checkout, stale tags and dirty manifest.
    with tempfile.TemporaryDirectory(prefix='deployment-release-') as directory:
        capture(['git', 'init', '-q', directory], 'Cannot initialize temporary Git repository.')
        capture(['git', '-C', directory, 'fetch', '--no-tags', origin, 'refs/tags/' + tag], 'Cannot fetch Release Tag.')
        fetched = capture(['git', '-C', directory, 'rev-parse', 'FETCH_HEAD^{commit}'], 'Cannot resolve fetched Tag.')
        require(fetched == commit, 'GitHub Tag/commit mismatch while fetching release.')
        text = capture(['git', '-C', directory, 'show', commit + ':.deploy/manifest.yaml'], 'Release manifest .deploy/manifest.yaml is missing.')
    manifest = parse_manifest(text)
    return dict(mode=mode, release=version, tag=tag, commit=commit, server=server, repository=repo, manifest=manifest)


def plan(config):
    m = config['manifest']
    print('Release: ' + config['release'] + '\nTag: ' + config['tag'] + '\nCommit: ' + config['commit'])
    print('\nDeployment Plan' if config['mode'] == 'deploy' else '\nVerification Plan (read-only)')
    for key, value in [('Application', m['application']['name']), ('Release', config['release']), ('Commit', config['commit']),
                       ('Server', config['server']), ('Deploy Path', m['server']['deploy_path']),
                       ('Compose', m['docker']['compose_file']), ('Image', m['docker']['image'] + ':' + config['release'])]:
        print(key + ': ' + value)
    print('\nRequired Environment:')
    for name in m['environment']['required']:
        print('- ' + name)
    print('\nRequired Directories:')
    for path in m['directories']['required']:
        print('- ' + path)
    print('\nHealth Check: ' + m['verify']['health']['url'], flush=True)


def read_environment(path, required):
    require(path.is_file() and os.access(path, os.R_OK), 'Server environment file is missing or unreadable.')
    values = {}
    # Deliberately a documented literal dotenv subset, never shell source/eval.
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        raise DeploymentError('Cannot read server environment file.') from None
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)', line)
        require(match, 'Unsupported environment file syntax; use single-line literal assignments.')
        name, value = match.groups()
        require(name not in values, 'Duplicate variable name in environment file.')
        if value.startswith("'"):
            match = re.fullmatch(r"'([^']*)'\s*(?:#.*)?", value)
            require(match, 'Unsupported quoted environment value.')
            value = match.group(1)
        elif value.startswith('"'):
            match = re.fullmatch(r'"([^"\\$]*)"\s*(?:#.*)?', value)
            require(match, 'Unsupported environment value: no interpolation or escapes in double quotes.')
            value = match.group(1)
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
            require(not any(c in value for c in '$`\\'), 'Unsupported environment value: quote literal values with single quotes.')
        require('\x00' not in value, 'Invalid environment file value.')
        values[name] = value
    for name in required:
        require(name in values and values[name] != '', name + ': MISSING or empty')
    return values


class Remote:
    def __init__(self, config):
        self.config = config
        self.m = config['manifest']
        self.repo = Path(self.m['server']['deploy_path']) / 'repository'
        self.envfile = Path(self.m['environment']['file'])
        self.secrets = []
        self.env = dict(os.environ)
        self.compose = ['docker', 'compose', '--project-name', self.m['application']['name'],
                        '--env-file', str(self.envfile), '-f', self.m['docker']['compose_file']]

    def safe(self, text):
        for value in self.secrets:
            text = text.replace(value, '[REDACTED]')
        # Strip terminal escapes/control bytes from externally generated logs.
        return ''.join(c for c in text if c in '\n\t' or ord(c) >= 32 and ord(c) != 127)

    def stream(self, args, label):
        print(label, flush=True)
        try:
            process = subprocess.Popen(args, cwd=self.repo, env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       encoding='utf-8', errors='replace', bufsize=1)
            for line in process.stdout:
                print(self.safe(line), end='', flush=True)
            status = process.wait()
        except OSError:
            raise DeploymentError(label + ' failed.') from None
        require(status == 0, label + ' failed.')

    def git(self, *args):
        return capture(['git', *args], 'Remote git ' + args[0] + ' failed.', cwd=self.repo)

    def directories(self):
        for directory in dict.fromkeys(self.m['directories']['required'] + self.m['verify']['directories']):
            path = Path(directory)
            require(path.is_dir() and os.access(path, os.R_OK | os.W_OK | os.X_OK), 'Required directory is missing or inaccessible.')
            require(not path.resolve().is_relative_to(self.repo.resolve()), 'Persistent directory must be outside repository.')

    def environment(self):
        require(not self.envfile.resolve().is_relative_to(self.repo.resolve()), 'Server environment file must be outside repository.')
        values = read_environment(self.envfile, self.m['environment']['required'])
        self.add_secrets([*values.values(), *os.environ.values()])
        reserved = {'PATH', 'HOME', 'PYTHONPATH', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'BASH_ENV', 'ENV'}
        require(not any(name in reserved or name.startswith(('DOCKER_', 'COMPOSE_')) for name in values),
                'Environment file contains a reserved runtime variable name.')
        # --env-file supplies values to Compose; inherited shell values must not override it.
        for name in values:
            self.env.pop(name, None)
        self.env['APP_VERSION'] = self.config['release']
        for name in list(self.env):
            if name.startswith('COMPOSE_'):
                del self.env[name]
        for name in self.m['environment']['required']:
            print(name + ': PRESENT', flush=True)

    def add_secrets(self, values):
        sensitive = {str(value) for value in values if value is not None and str(value)}
        for value in list(sensitive):
            try:
                url = urlsplit(value)
                if url.scheme and url.hostname:
                    if url.password:
                        sensitive.update((url.password, unquote(url.password)))
                    sensitive.update(item for _, item in parse_qsl(url.query) if item)
            except ValueError:
                pass
        variants = {encoded for value in sensitive for encoded in
                    (value, quote(value, safe=''), quote_plus(value), json.dumps(value)[1:-1])}
        self.secrets = sorted(set(self.secrets) | variants, key=len, reverse=True)

    def precheck(self):
        require(sys.version_info >= (3, 9), 'Remote Python 3.9+ is required.')
        print('\nSSH connectivity: PASS\nRemote precheck\nPython 3.9+: PRESENT', flush=True)
        for tool, args in [('git', ['--version']), ('docker', ['--version']), ('curl', ['--version'])]:
            require(shutil.which(tool), 'Remote ' + tool + ' is required.')
            capture([tool, *args], 'Remote ' + tool + ' is unavailable.')
            print(tool + ': PRESENT', flush=True)
        capture(['docker', 'compose', 'version'], 'Remote docker compose is unavailable.')
        require(not os.environ.get('DOCKER_HOST'), 'DOCKER_HOST override is not supported; use the SSH server local Docker daemon.')
        endpoint = capture(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'], 'Cannot inspect Docker context.')
        require(endpoint.startswith('unix:///'), 'Docker context must use a local Unix socket.')
        capture(['docker', 'info'], 'Remote docker daemon is unavailable.')
        require(self.repo.parent.is_dir() and os.access(self.repo.parent, os.R_OK | os.X_OK), 'deploy_path is missing or inaccessible.')
        require(self.repo.is_dir(), 'deploy_path/repository is missing.')
        require(self.git('rev-parse', '--is-inside-work-tree') == 'true', 'Remote repository is not a Git working tree.')
        require(Path(self.git('rev-parse', '--show-toplevel')).resolve() == self.repo.resolve(), 'Remote repository must be its Git root.')
        require(github_repo(self.git('remote', 'get-url', 'origin')) == self.config['repository'], 'Remote origin repository mismatch.')
        require(not self.git('status', '--porcelain', '--untracked-files=all'), 'Remote working tree is not clean.')
        self.environment()
        self.directories()
        for path in (self.repo, Path(capture(['docker', 'info', '--format', '{{.DockerRootDir}}'], 'Cannot determine Docker data directory.'))):
            require(path.is_absolute() and path.is_dir(), 'Docker/repository disk path is inaccessible.')
            free = shutil.disk_usage(path).free
            print('Disk free: ' + str(free // (1024 ** 2)) + ' MiB', flush=True)
            require(free >= MIN_FREE_BYTES, 'Insufficient disk space: at least 1024 MiB required on repository and Docker filesystems.')
        print('Precheck: PASS', flush=True)

    def compose_check(self):
        path = (self.repo / self.m['docker']['compose_file']).resolve()
        require(path.is_file() and path.is_relative_to(self.repo.resolve()), 'Compose file missing or outside repository.')
        try:
            data = json.loads(capture(self.compose + ['config', '--format', 'json'], 'Invalid Docker Compose configuration.', cwd=self.repo, env=self.env))
            services = data['services']
            for service in services.values():
                self.add_secrets((service.get('environment') or {}).values())
                build = service.get('build')
                if isinstance(build, dict):
                    self.add_secrets((build.get('args') or {}).values())
            require(all(name in services for name in self.m['verify']['services']), 'Required service is missing from Compose configuration.')
            expected = self.m['docker']['image'] + ':' + self.config['release']
            require(any(service.get('image') == expected and service.get('build') for service in services.values()),
                    'Compose must build the manifest image with the release version via APP_VERSION.')
            for service in services.values():
                image = service.get('image', '')
                require(isinstance(image, str) and ':' in image.rsplit('/', 1)[-1]
                        and image.rsplit(':', 1)[-1] != 'latest', 'Compose image must have an explicit version, never latest.')
                for mount in service.get('volumes', []):
                    if mount.get('type') == 'bind':
                        source = Path(mount.get('source', ''))
                        require(source.is_absolute() and source.exists() and os.access(source, os.R_OK),
                                'Compose bind source is missing or inaccessible; create it manually before deployment.')
                        require(mount.get('bind', {}).get('create_host_path') is False,
                                'Compose bind mounts must set bind.create_host_path: false (long syntax).')
                    elif mount.get('type') == 'volume':
                        definition = data.get('volumes', {}).get(mount.get('source'), {})
                        require(definition.get('external') is True and definition.get('name'),
                                'Persistent named volumes must be pre-existing external volumes; anonymous volumes are unsupported.')
                        capture(['docker', 'volume', 'inspect', definition['name']], 'Required external Docker volume is missing.')
                    else:
                        require(mount.get('type') == 'tmpfs', 'Unsupported Compose mount type.')
        except (ValueError, KeyError, TypeError, AttributeError):
            raise DeploymentError('Invalid Docker Compose configuration response.') from None

    def retry(self, check):
        for attempt in range(3):
            try:
                check()
                return
            except DeploymentError:
                if attempt == 2:
                    raise
                time.sleep(1)

    def verify(self):
        require(self.git('rev-parse', 'HEAD') == self.config['commit'], 'Git Commit: FAIL')
        def containers():
            running = capture(self.compose + ['ps', '--status', 'running', '--services'], 'Containers: FAIL', cwd=self.repo, env=self.env).splitlines()
            require(set(self.m['verify']['services']).issubset(running), 'Containers: FAIL (required services are not running)')
        self.retry(containers)
        self.environment()
        self.directories()
        health = self.m['verify']['health']
        def health_check():
            status = capture(['curl', '--disable', '--silent', '--output', '/dev/null', '--write-out', '%{http_code}',
                              '--connect-timeout', '3', '--max-time', '5', '--noproxy', '*', health['url']], 'Health Check: FAIL (request failed)')
            require(status == str(health['status']), 'Health Check: FAIL (unexpected HTTP status)')
        self.retry(health_check)
        print('\n================================\nDEPLOYMENT RESULT\n================================')
        for name, value in [('Application', self.m['application']['name']), ('Release', self.config['release']),
                            ('Commit', self.config['commit']), ('Server', self.config['server'])]:
            print(name + ': ' + value)
        print('\nDeployment:\n' + ('PASS' if self.config['mode'] == 'deploy' else 'NOT RUN (verification only)'))
        print('\nAutomatic Verification:\nGit Commit        PASS\nContainers        PASS\nEnvironment       PASS\nDirectories       PASS\nHealth Check      PASS')
        print('\n5 / 5 PASSED\n\nStatus:\nAWAITING MANUAL VERIFICATION\n\nManual verification is still required.', flush=True)

    def run(self):
        stage = 'DEPLOYMENT BLOCKED'
        try:
            self.precheck()
            if self.config['mode'] == 'deploy':
                stage = 'DEPLOYMENT FAILED'
                print('Fetch origin tags', flush=True)
                self.git('fetch', 'origin', '--tags')
                tag_commit = self.git('rev-parse', '--verify', 'refs/tags/' + self.config['tag'] + '^{commit}')
                require(tag_commit == self.config['commit'], 'Server Tag/commit mismatch.')
                self.git('-c', 'core.hooksPath=/dev/null', 'checkout', '--detach', self.config['commit'])
                require(self.git('rev-parse', 'HEAD') == self.config['commit'], 'Checkout commit mismatch.')
                print('Checkout exact commit: ' + self.config['commit'], flush=True)
                self.compose_check()
                self.stream(self.compose + ['build'], 'Docker build')
                self.stream(self.compose + ['up', '-d', '--no-build', '--pull', 'never'], 'Docker start')
                self.stream(self.compose + ['ps'], 'Docker Compose ps')
            else:
                self.compose_check()
            stage = 'DEPLOYMENT FAILED'
            self.verify()
        except (DeploymentError, OSError) as error:
            message = str(error) if isinstance(error, DeploymentError) else 'Remote filesystem operation failed.'
            print(stage + ': ' + message, file=sys.stderr, flush=True)
            return 2 if stage == 'DEPLOYMENT BLOCKED' else 1
        return 0


def main():
    try:
        require(len(sys.argv) == 4 and sys.argv[1] in ('deploy', 'verify'), 'Usage: deploy.sh <version> <server>')
        config = local_config(*sys.argv[1:])
        plan(config)
        # No remote temporary files or interpolated shell fragments. Source is trusted
        # skill code; config is serialized as data, never executable manifest content.
        source = Path(__file__).read_text(encoding='utf-8')
        payload = 'REMOTE_CONFIG = ' + repr(config) + '\n' + source
        result = subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes',
                                 '--', config['server'],
                                 'command -v python3 >/dev/null 2>&1 || { printf "DEPLOYMENT BLOCKED: remote python3 is required.\\n" >&2; exit 2; }; exec python3 -u -'], input=payload, text=True)
        if result.returncode != 0:
            if result.returncode == 255:
                print('DEPLOYMENT BLOCKED: SSH unavailable or disconnected. Remote outcome may be unknown; inspect before retrying.', file=sys.stderr)
            elif result.returncode in (2, 127):
                print('DEPLOYMENT BLOCKED: remote precheck or dependency check failed; see output above.', file=sys.stderr)
            else:
                print('DEPLOYMENT FAILED: remote execution failed; see output above. No automatic recovery performed.', file=sys.stderr)
            return 1
    except (DeploymentError, OSError) as error:
        message = str(error) if isinstance(error, DeploymentError) else 'Local execution failed.'
        print('DEPLOYMENT BLOCKED: ' + message, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    if 'REMOTE_CONFIG' in globals():
        sys.exit(Remote(REMOTE_CONFIG).run())
    sys.exit(main())
