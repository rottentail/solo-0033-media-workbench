"""Freeze listener poses for first-order soundfields on a continuous sample clock."""
import hashlib
import json
import math
from . import db, media_sources, timeline

RATE = 48000


def unit(values):
    if len(values) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('pose must be a finite quaternion [w,x,y,z]')
    norm = math.sqrt(sum(v*v for v in values))
    if norm < 1e-12:
        raise ValueError('pose quaternion has no orientation')
    return [v/norm for v in values]


def poses(keyframes, duration_ms):
    if not isinstance(keyframes, list) or not 2 <= len(keyframes) <= 64:
        raise ValueError('two to sixty-four listener poses required')
    result = []
    for item in keyframes:
        at = item['at_ms']
        if type(at) is not int or not 0 <= at <= duration_ms or result and at*48 <= result[-1]['sample']:
            raise ValueError('pose times must strictly increase within the programme')
        result.append({'sample': at*48, 'q': unit(item['q'])})
    if result[0]['sample'] != 0 or result[-1]['sample'] != duration_ms*48:
        raise ValueError('poses must cover the trimmed programme')
    return result


def orientation(plan, sample):
    points = plan['poses']
    if not 0 <= sample <= plan['samples']:
        raise ValueError('pose outside programme')
    for left, right in zip(points, points[1:]):
        if sample <= right['sample']:
            t = (sample-left['sample'])/(right['sample']-left['sample'])
            a, b = left['q'], right['q']
            dot = sum(x*y for x, y in zip(a, b))
            if dot < 0:
                b, dot = [-x for x in b], -dot
            dot = min(1.0, max(-1.0, dot))
            if dot > .9995:
                return unit([(1-t)*x+t*y for x, y in zip(a, b)])
            angle = math.acos(dot)
            first = math.sin((1-t)*angle)/math.sin(angle)
            second = math.sin(t*angle)/math.sin(angle)
            return [first*x+second*y for x, y in zip(a, b)]
    return list(points[-1]['q'])


def angular_distance(a, b):
    cosine = abs(sum(x*y for x, y in zip(a, b)))
    return 2*math.acos(min(1, max(0, cosine)))


def compact(points, limit):
    if type(limit) is not int or not 2 <= limit <= 64:
        raise ValueError('pose capacity must be two to sixty-four')
    if len(points) <= limit:
        return points, 0.0
    errors = {}
    for i in range(len(points)-1):
        for j in range(i+1, len(points)):
            segment = {'poses': [points[i], points[j]], 'samples': points[j]['sample']}
            errors[i, j] = max((angular_distance(points[k]['q'], orientation(segment, points[k]['sample']))
                               for k in range(i+1, j)), default=0.0)
    # Bottleneck dynamic programming. A local error winner need not leave the
    # best use of the remaining pose capacity for the rest of the trajectory.
    states = {(1, 0): (0.0, (0,))}
    for count in range(2, limit+1):
        for end in range(count-1, len(points)):
            choices = []
            for previous in range(count-2, end):
                old = states.get((count-1, previous))
                if old is not None:
                    choices.append((max(old[0], errors[previous, end]), old[1]+(end,)))
            if choices:
                states[count, end] = min(choices)
    error, selected = min(states[count, len(points)-1] for count in range(2, limit+1))
    return [points[index] for index in selected], math.degrees(error)


def create(conn, project_id, asset_id, start_ms, end_ms, convention, keyframes, max_poses=64):
    if (type(start_ms) is not int or type(end_ms) is not int or start_ms < 0
            or not 1 <= end_ms-start_ms <= 30000):
        raise ValueError('spatial trim must span one millisecond to thirty seconds')
    if convention not in ('ambix', 'fuma'):
        raise ValueError('input convention must be ambix or fuma')
    asset = media_sources.get(conn, asset_id)
    metadata = json.loads(asset['metadata'])
    stream = next((s for s in metadata['streams'] if s['codec_type'] == 'audio'), {})
    if stream.get('channels') != 4 or float(metadata['format']['duration'])*1000+.001 < end_ms:
        raise ValueError('a four-channel recording covering the trim is required')
    clip = {k: asset[k] for k in ('path', 'fingerprint', 'metadata')}
    clip.update(asset_id=asset_id, start_ms=start_ms, end_ms=end_ms, has_audio=True, gain=1)
    original = poses(keyframes, end_ms-start_ms)
    selected, error = compact(original, max_poses)
    plan = {'version': 1, 'project': timeline.snapshot(conn, project_id)['project'],
            'clips': [clip], 'convention': convention, 'samples': (end_ms-start_ms)*48,
            'poses': selected, 'original_poses': original, 'max_poses': max_poses,
            'max_error_deg': error, 'rate': RATE,
            'output_convention': 'ACN/SN3D', 'listener_axes': 'X-front,Y-left,Z-up'}
    payload = json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False)
    with db.write(conn):
        cursor = conn.execute('INSERT INTO spatial_plans(project_id,payload,payload_sha256) VALUES (?,?,?)',
                              (project_id, payload, hashlib.sha256(payload.encode()).hexdigest()))
    return get(conn, cursor.lastrowid)


def get(conn, plan_id):
    row = conn.execute('SELECT * FROM spatial_plans WHERE id=?', (plan_id,)).fetchone()
    if row is None or hashlib.sha256(row['payload'].encode()).hexdigest() != row['payload_sha256']:
        raise ValueError('spatial plan is missing or damaged')
    return dict(json.loads(row['payload']), id=plan_id)
