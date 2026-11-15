"""Build a render plan from a frozen timeline."""
import json
from .assets import fingerprint

def prepare(snapshot):
    clips = snapshot['clips']
    if not clips:
        raise ValueError('timeline is empty')
    for clip in clips:
        if fingerprint(clip['path']) != clip['fingerprint']:
            raise ValueError('source changed since intake')
        streams = json.loads(clip['metadata'])['streams']
        if not any(s.get('codec_type') == 'video' for s in streams):
            raise ValueError('each clip must contain video')
        clip['has_audio'] = any(s.get('codec_type') == 'audio' for s in streams)
    return snapshot
