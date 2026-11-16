"""Write one bounded portable archive from frozen, retained proxy receipts."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile
from . import bundle_plan, bundle_select
from .assets import fingerprint


def write_media(archive, name, receipt):
    digest = hashlib.sha256()
    count = 0
    with open(receipt['path'], 'rb') as source, archive.open(name, 'w', force_zip64=True) as output:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            digest.update(chunk)
            count += len(chunk)
            output.write(chunk)
    if count != receipt['size'] or digest.hexdigest() != receipt['fingerprint']:
        raise ValueError('proxy changed while creating the offline package')
    return count


def create(conn, projects, max_media_bytes, destination):
    if type(max_media_bytes) is not int or max_media_bytes < 0:
        raise ValueError('media capacity must be a nonnegative integer')
    destination = Path(destination).expanduser().absolute()
    destination = destination.parent.resolve()/destination.name
    if os.path.lexists(destination) or not destination.parent.is_dir():
        raise ValueError('destination exists or its directory is missing')
    with ExitStack() as stack:
        plan = bundle_plan.capture(conn, projects, stack)
        sizes = {key: value['size'] for key, value in plan['media'].items()}
        selection = bundle_select.choose(plan['projects'], sizes, max_media_bytes)
        keep = {plan['media'][key]['path'] for key in selection['media']}
        for path, handle in plan['locks'].items():
            if path not in keep:
                handle.close()
        description = bundle_plan.manifest(plan, selection)
        with tempfile.TemporaryDirectory(prefix='.offline-bundle-', dir=destination.parent) as directory:
            output = Path(directory)/'package.zip'
            actual = 0
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
                for key in selection['media']:
                    actual += write_media(archive, 'media/'+key+'.mp4', plan['media'][key])
                if actual > max_media_bytes or actual != selection['media_bytes']:
                    raise ValueError('package byte allocation no longer matches its contents')
                archive.writestr('manifest.json', json.dumps(description, sort_keys=True,
                    ensure_ascii=False, separators=(',', ':'), allow_nan=False))
            with output.open('rb') as handle:
                os.fsync(handle.fileno())
            checksum = fingerprint(output)
            os.link(output, destination)
    return {'output_path': str(destination), 'sha256': checksum,
            'project_ids': selection['project_ids'], 'value': selection['value'],
            'media_bytes': actual, 'unavailable': plan['unavailable']}
