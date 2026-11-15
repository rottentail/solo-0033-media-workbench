"""Normalize each segment before concatenation."""
from pathlib import Path
from .tools import run

def render(snapshot, temporary_dir):
    temp = Path(temporary_dir)
    segments = []
    for i, c in enumerate(snapshot['clips']):
        segment = temp / f'{i:06}.mp4'
        duration = (c['end_ms'] - c['start_ms']) / 1000
        args = ['-v','error','-y','-ss',str(c['start_ms']/1000),'-i',c['path']]
        if not c['has_audio']:
            args += ['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000']
        args += ['-t',str(duration),'-map','0:v:0','-map', '0:a:0' if c['has_audio'] else '1:a:0', '-vf','scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,fps=25,setsar=1','-af',f"volume={c['gain']},aresample=48000",'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-ac','2','-ar','48000','-shortest',str(segment)]
        run('ffmpeg', args)
        segments.append(segment)
    listing = temp / 'segments.txt'
    listing.write_text(''.join(f"file '{p.name}'\n" for p in segments), encoding='utf-8')
    output = temp / 'result.mp4'
    run('ffmpeg', ['-v','error','-y','-f','concat','-safe','1','-i',str(listing),'-c','copy','-movflags','+faststart',str(output)])
    return output
