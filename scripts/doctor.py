"""Read-only team preflight. Does not install software, read keys, or contact a model."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def probe(label, command):
    if not shutil.which(command[0]):
        print(f'OPTIONAL MISSING: {label}')
        return
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=12)
        if result.returncode:
            print(f'OPTIONAL NOT READY: {label}')
        else:
            print(f'AVAILABLE: {label}: {result.stdout.strip().splitlines()[0]}')
    except (subprocess.TimeoutExpired, IndexError):
        print(f'OPTIONAL NOT READY: {label}')


def main():
    print(f'Python {sys.version.split()[0]}')
    if sys.version_info < (3, 10):
        raise SystemExit('Use Python 3.10+ for the preparation scripts')
    for label, command in [('Git', ['git', '--version']), ('Node', ['node', '--version']),
                           ('npm', ['npm', '--version']), ('Docker CLI', ['docker', '--version']),
                           ('Docker Compose', ['docker', 'compose', 'version']),
                           ('Docker engine', ['docker', 'info', '--format', '{{.ServerVersion}}'])]:
        probe(label, command)
    for script, flags in [('check_handoff.py', ['--self-test']), ('preview.py', ['--check'])]:
        result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script), *flags], cwd=ROOT)
        if result.returncode:
            raise SystemExit(result.returncode)
    print('PASS: starter-kit checks. This does not certify the future live platform.')
    print('Node/npm are for Member 1; Docker is for lab/integration work. Missing tools do not block the static preview.')
    print('Next: docs/weekend/START_HERE.md')


if __name__ == '__main__':
    main()
