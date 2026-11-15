"""External process integration, with timeouts and bounded diagnostics."""
import os
import shutil
import subprocess

class ToolError(ValueError):
    pass

def binary(name):
    candidate = os.environ.get('MEDIA_' + name.upper()) or shutil.which(name)
    if not candidate or not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
        raise ToolError(f'{name} unavailable; set MEDIA_{name.upper()} to its executable')
    return candidate

def run(name, arguments, timeout=120):
    try:
        result = subprocess.run([binary(name), *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f'{name} timed out') from exc
    if result.returncode:
        raise ToolError(result.stderr.decode('utf-8', 'replace')[-4000:])
    return result.stdout
