# Media Workbench

A Python HTTP service for assembling media segments into a normalized MP4. It probes source media, persists projects and ordered clips in SQLite, freezes each render plan, checks input fingerprints and atomically publishes a render. Clips without audio receive a silent audio track; video is normalized to 640×360 at 25 fps and audio to stereo 48 kHz.

## Requirements and startup

Python 3.10+ and FFmpeg/FFprobe with libx264 and AAC support. Set `MEDIA_FFMPEG` and `MEDIA_FFPROBE` to executable paths if they are not in PATH. Run `python3 -m mediaworkbench.server`; the server listens on 127.0.0.1:8765. `MEDIA_PORT` and `MEDIA_DATABASE` override the port and SQLite path. This is a trusted local operator service: it has no authentication and can read source paths and write output paths accessible to its process. Keep it bound to loopback.

POST JSON to `/assets` with `{"path":"/absolute/input.mp4"}`, `/projects` with `{"name":"Example"}`, `/clips` with `{"project_id":1,"asset_id":1,"start_ms":0,"end_ms":1000,"gain":1}`, then `/renders` with `{"project_id":1,"destination":"/absolute/output.mp4"}`. GET `/projects/1` inspects the timeline; GET `/renders/1` inspects render status. The render request runs synchronously. Existing output paths are rejected. Source files must remain unchanged after intake. Rendering produces a single MP4, not a non-destructive editor or arbitrary codec pipeline.

Automated tests are deferred. Validate using bounded media examples and inspect outputs with ffprobe.
