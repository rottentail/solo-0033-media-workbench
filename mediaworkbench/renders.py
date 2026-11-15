"""Render state and atomic publication of outputs."""
import json
import os
import tempfile
from pathlib import Path
from . import timeline, planner, encoder

def create(conn, project_id, destination):
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise ValueError('destination already exists')
    if not destination.parent.is_dir():
        raise ValueError('destination directory does not exist')
    frozen = planner.prepare(timeline.snapshot(conn, project_id))
    with conn:
        cur = conn.execute('INSERT INTO renders(project_id,revision,status,snapshot) VALUES (?,?,?,?)', (project_id, frozen['project']['revision'], 'running', json.dumps(frozen)))
    render_id = cur.lastrowid
    try:
        with tempfile.TemporaryDirectory(prefix='.media-render-', dir=destination.parent) as tmp:
            output = encoder.render(frozen, tmp)
            # Hard link makes publication fail if a concurrent writer created the destination.
            os.link(output, destination)
        with conn:
            conn.execute('UPDATE renders SET status=?,output_path=? WHERE id=?', ('completed',str(destination),render_id))
    except Exception as exc:
        with conn:
            conn.execute('UPDATE renders SET status=?,error=? WHERE id=?', ('failed',str(exc)[:4000],render_id))
        raise
    return {'id': render_id, 'status': 'completed', 'output_path': str(destination), 'revision': frozen['project']['revision']}

def get(conn, render_id):
    row = conn.execute('SELECT * FROM renders WHERE id=?', (render_id,)).fetchone()
    if not row:
        raise ValueError('render not found')
    return dict(row)
