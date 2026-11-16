"""Resolve immutable asset identity separately from original and proxy locations."""
import copy
import json
from pathlib import Path
from .assets import fingerprint
from .tools import run


def stamp(path):
    info = Path(path).stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def inspect(path):
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('media location must be a regular file')
    before = stamp(path)
    checksum = fingerprint(path)
    metadata = json.loads(run('ffprobe', ['-v', 'error', '-show_format',
        '-show_streams', '-of', 'json', str(path)]))
    if stamp(path) != before or fingerprint(path) != checksum:
        raise ValueError('media changed while inspecting its location')
    return {'path': str(path), 'fingerprint': checksum,
            'metadata': metadata, 'stamp': before}


def get(conn, asset_id):
    row = conn.execute('SELECT assets.*,COALESCE(asset_links.revision,0) AS link_revision '
        'FROM assets LEFT JOIN asset_links ON asset_links.asset_id=assets.id '
        'WHERE assets.id=?', (asset_id,)).fetchone()
    if row is None:
        raise ValueError('asset not found')
    result = dict(row)
    proxy = conn.execute('SELECT * FROM asset_proxies WHERE asset_id=?', (asset_id,)).fetchone()
    result['proxy'] = dict(proxy) if proxy else None
    return result


def select(conn, occurrence, purpose='final', tick=None, validated=None):
    if purpose not in ('preview', 'final'):
        raise ValueError('unknown media purpose')
    asset = get(conn, occurrence['asset_id'])
    if asset['fingerprint'] != occurrence['fingerprint']:
        raise ValueError('frozen asset identity no longer matches the catalog')
    clip = copy.deepcopy(occurrence)
    proxy = asset['proxy']

    def matches(path, checksum):
        identity = (path, checksum)
        if validated is not None and identity in validated:
            return True
        if fingerprint(path, tick) != checksum:
            return False
        if validated is not None:
            validated.add(identity)
        return True

    if purpose == 'preview' and proxy and proxy['path']:
        try:
            if (proxy['source_fingerprint'] == asset['fingerprint']
                    and matches(proxy['path'], proxy['fingerprint'])):
                clip.update(path=proxy['path'], fingerprint=proxy['fingerprint'],
                    metadata=proxy['metadata'], rendition='proxy',
                    source_fingerprint=asset['fingerprint'])
                return clip
        except OSError:
            pass
    if not matches(asset['path'], asset['fingerprint']):
        raise ValueError('original source changed since intake')
    clip.update(path=asset['path'], metadata=asset['metadata'], rendition='original')
    return clip


def bind(conn, snapshot, purpose='final', tick=None):
    result = copy.deepcopy(snapshot)
    validated = set()
    result['clips'] = [select(conn, clip, purpose, tick, validated) for clip in snapshot['clips']]
    return result
