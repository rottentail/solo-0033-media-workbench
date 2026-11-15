"""Timeline revisions, clip bounds and order."""
import json
import math

def project(conn, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('name is required')
    with conn:
        cur = conn.execute('INSERT INTO projects(name) VALUES (?)', (name.strip(),))
    return {'id': cur.lastrowid, 'revision': 0}

def add_clip(conn, project_id, asset_id, start_ms, end_ms, gain=1.0):
    if type(start_ms) is not int or type(end_ms) is not int or start_ms < 0 or end_ms <= start_ms:
        raise ValueError('invalid clip boundaries')
    if not isinstance(gain, (float, int)) or not math.isfinite(gain) or not 0 <= gain <= 2:
        raise ValueError('gain must be between 0 and 2')
    with conn:
        asset = conn.execute('SELECT metadata FROM assets WHERE id=?', (asset_id,)).fetchone()
        p = conn.execute('SELECT revision FROM projects WHERE id=?', (project_id,)).fetchone()
        if not asset or not p:
            raise ValueError('project or asset not found')
        duration = float(json.loads(asset['metadata'])['format']['duration']) * 1000
        if end_ms > round(duration):
            raise ValueError('clip exceeds source duration')
        position = conn.execute('SELECT count(*) FROM clips WHERE project_id=?', (project_id,)).fetchone()[0]
        cur = conn.execute('INSERT INTO clips(project_id,asset_id,start_ms,end_ms,position,gain) VALUES (?,?,?,?,?,?)', (project_id, asset_id, start_ms, end_ms, position, gain))
        conn.execute('UPDATE projects SET revision=revision+1 WHERE id=?', (project_id,))
    return {'id': cur.lastrowid, 'revision': p['revision'] + 1}

def snapshot(conn, project_id):
    conn.execute('SAVEPOINT timeline_read')
    try:
        p = conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        if not p:
            raise ValueError('project not found')
        clips = [dict(r) for r in conn.execute('SELECT clips.*,assets.path,assets.fingerprint,assets.metadata FROM clips JOIN assets ON assets.id=clips.asset_id WHERE project_id=? ORDER BY position,id', (project_id,))]
        return {'project': dict(p), 'clips': clips}
    finally:
        conn.execute('RELEASE SAVEPOINT timeline_read')
