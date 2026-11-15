"""Run a bounded production workflow on generated media."""
import tempfile
from pathlib import Path
from . import db, assets, timeline, renders
from .tools import run

def main():
    with tempfile.TemporaryDirectory(prefix='media-check-') as directory:
        root = Path(directory)
        source = root / 'source.mp4'
        run('ffmpeg', ['-v','error','-y','-f','lavfi','-i','testsrc=size=160x90:rate=25','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)])
        conn = db.connect(root / 'data.sqlite3')
        asset = assets.register(conn, source)
        project = timeline.project(conn, 'Example timeline')
        timeline.add_clip(conn,project['id'],asset['id'],0,1000,0.5)
        timeline.add_clip(conn,project['id'],asset['id'],1000,2000)
        result = renders.create(conn,project['id'],root/'output.mp4')
        import json
        probe = json.loads(run('ffprobe',['-v','error','-show_streams','-show_format','-of','json', result['output_path']]))
        assert 1.9 < float(probe['format']['duration']) < 2.2
        assert {s['codec_type'] for s in probe['streams']} >= {'video','audio'}
        assert renders.get(conn,result['id'])['status'] == 'completed'
        print('Media workflow passed: two clips, audio and video, 2 seconds.')
        conn.close()

if __name__ == '__main__': main()
