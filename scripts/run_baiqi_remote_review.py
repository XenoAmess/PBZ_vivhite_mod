"""Run the BaiQi motion render preset on the LAN worker, with a local fallback."""
import argparse
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FORMS = ('coat_on', 'coat_off')
VIEWS = ('front', 'back', 'side', 'oblique')
NATIVE_CASES = ('Hun_Unarmed_Idle_Loop', 'Hun_Unarmed_Run_Fwd_Loop', 'Hun_BaiShanDual_Attack_A')
DEFAULT_CASES = ('arms_forward', 'arms_abduction', 'Hun_BaiShanDual_Attack_A')
SUITE = ROOT / 'qa/suites/humanoid_v1_1.json'
RUNNER = ROOT / 'scripts/run_baiqi_cc0_motion_review.py'
REMOTE_RECIPE = 'fb7e7cf55f4753d8f81242b7afc62d9ae8338f6e'
# The LAN gateway must be reached directly even when a general HTTPS proxy is set.
HTTP = build_opener(ProxyHandler({}))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def request(base, path, *, method='GET', payload=None, headers=None, timeout=8):
    headers = dict(headers or {})
    token = os.environ.get('PBZ_RENDER_SERVICE_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if isinstance(payload, dict):
        payload = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    return HTTP.open(Request(base + path, data=payload, headers=headers, method=method), timeout=timeout)


def response_json(base, path, **kwargs):
    with request(base, path, **kwargs) as response:
        return json.load(response)


def inputs_zip(path, models, donor, control, cases):
    assets = {'forms': {form: f'forms/{form}.blend' for form in models},
              'donor': 'donor/Delta_SelfTest.blend', 'cc0_control': 'Base_Female.blend',
              'animations': {clip: f'animations/{clip}.ueanim' for clip in cases if clip in NATIVE_CASES}}
    files = {assets['donor']: donor, 'donor/sampling_report.json': donor.with_name('sampling_report.json'),
             assets['cc0_control']: control}
    files.update((assets['forms'][form], file) for form, file in models.items())
    files.update((name, ROOT / 'repro/game_reference' / name) for name in assets['animations'].values())
    if sum(file.stat().st_size for file in files.values()) > 6 * 1024**3:
        raise ValueError('Review inputs exceed the worker unpacked size limit.')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as out:
        out.writestr(zipfile.ZipInfo('manifest.json'), json.dumps(assets, sort_keys=True))
        for name, local_file in sorted(files.items()):
            entry = zipfile.ZipInfo(name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.file_size = local_file.stat().st_size
            with local_file.open('rb') as source, out.open(entry, 'w') as destination:
                shutil.copyfileobj(source, destination)
    if path.stat().st_size > 2 * 1024**3:
        raise ValueError('Review ZIP exceeds the worker upload limit.')


def extract_verified(path, output, digest, params, models, donor, control):
    with zipfile.ZipFile(path) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        expected_images = 2 * len(models) * len(params['cases']) * len(params['sample_indices']) * len(params['views'])
        expected = {'input_sha256': digest, 'source_commit': REMOTE_RECIPE, 'params': params,
                    'model_sha256': {name: sha(file) for name, file in models.items()},
                    'suite_sha256': sha(SUITE), 'donor_sha256': sha(donor),
                    'cc0_control_sha256': sha(control), 'images': expected_images}
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError('Render manifest does not match the submitted review inputs.')
        reports = {f'{form}/motion_report.json' for form in models}
        entries = manifest['files']
        if len({entry['path'] for entry in entries}) != len(entries):
            raise ValueError('Duplicate file in renderer manifest.')
        names = {entry['path'] for entry in entries}
        zip_names = bundle.namelist()
        if (len(zip_names) != len(set(zip_names)) or set(zip_names) != names | {'manifest.json'}
                or not reports <= names or sum(name.endswith('.png') for name in names) != expected_images):
            raise ValueError('Render ZIP does not have the expected files.')
        output.mkdir()
        for entry in entries:
            name = entry['path']
            relative = PurePosixPath(name)
            target = output / relative
            if (relative.is_absolute() or not relative.parts or '..' in relative.parts
                    or any(c in name for c in ('\\', ':')) or not target.resolve().is_relative_to(output)):
                raise ValueError(f'Invalid path in renderer manifest: {name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(name) as source, target.open('xb') as destination:
                shutil.copyfileobj(source, destination)
            if target.stat().st_size != entry['bytes'] or sha(target) != entry['sha256']:
                raise ValueError(f'Render file failed integrity check: {name}')
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def run_remote(args, params, models, work):
    base = args.service_url.rstrip('/')
    address = urlsplit(base)
    if (address.scheme not in ('http', 'https') or not address.hostname
            or address.username or address.path or address.query or address.fragment):
        raise ValueError('Supply the HTTP(S) service origin without credentials in the URL.')
    state = response_json(base, '/v1/service/status')
    if not state.get('ready') or not state.get('accepting_jobs'):
        raise RuntimeError('The unified service is not accepting work.')
    models_list = response_json(base, '/v1/models')['data']
    if not any(row['id'] == 'blender-review' and row.get('configured') for row in models_list):
        raise RuntimeError('The unified service has no configured Blender worker.')
    archive = work / 'input.zip'
    inputs_zip(archive, models, args.donor, args.cc0_control, params['cases'])
    digest = sha(archive)
    with archive.open('rb') as stream, request(base, f'/v1/render/assets/{digest}', method='PUT',
            payload=stream, headers={'Content-Type': 'application/zip', 'Content-Length': str(archive.stat().st_size)},
            timeout=25) as response:
        response.read()
    body = {'kind': 'blender_review', 'source_commit': REMOTE_RECIPE, 'input_sha256': digest, 'params': params}
    headers = {'Idempotency-Key': 'pbz-' + uuid.uuid4().hex}
    try:
        job = response_json(base, '/v1/render/jobs', method='POST', payload=body, headers=headers)
    except HTTPError:
        raise
    except (OSError, HTTPException):
        job = response_json(base, '/v1/render/jobs', method='POST', payload=body, headers=headers)
    job_id = job['job_id']
    if not re.fullmatch(r'render_[a-zA-Z0-9_-]+', job_id):
        raise ValueError('Unexpected Blender job ID.')
    endpoint = f'/v1/render/jobs/{job_id}'
    started = last_update = time.monotonic()
    progress = None
    print(f'Remote Blender job {job_id}', flush=True)
    try:
        while True:
            job = response_json(base, endpoint)
            status = job['status']
            if status == 'completed':
                break
            if status in ('failed', 'cancelled'):
                raise RuntimeError(f'Remote render {status}: {job.get("error")}')
            now = time.monotonic()
            if job.get('progress') != progress:
                progress = job.get('progress')
                last_update = now
            if status == 'queued' and now - started >= args.queue_timeout:
                raise TimeoutError(f'Remote queue exceeded {args.queue_timeout} seconds.')
            if now - last_update >= args.stall_timeout:
                raise TimeoutError(f'Remote render reported no progress for {args.stall_timeout} seconds.')
            if now - started > args.queue_timeout + params['timeout_seconds'] + 30:
                raise TimeoutError('Remote render exceeded its total budget.')
            time.sleep(2)
    except (OSError, RuntimeError, ValueError, KeyError, HTTPException, KeyboardInterrupt):
        try:
            with request(base, endpoint, method='DELETE', timeout=3):
                pass
        except (OSError, HTTPException):
            pass
        raise
    result_file = work / 'result.zip'
    with request(base, endpoint + '/result', timeout=25) as response, result_file.open('wb') as output:
        declared_hash = response.headers.get('X-Result-SHA256')
        shutil.copyfileobj(response, output, length=1024 * 1024)
    result_sha = sha(result_file)
    result_info = job['result']
    if (declared_hash != result_sha or result_info['sha256'] != result_sha
            or result_info['bytes'] != result_file.stat().st_size):
        raise ValueError('Result ZIP did not match the HTTP or job metadata.')
    manifest = extract_verified(result_file, work / 'result', digest, params, models, args.donor, args.cc0_control)
    return {'backend': 'remote', 'job_id': job_id, 'result_sha256': result_sha, 'input_sha256': digest,
            'queue_seconds': job.get('queue_seconds'), 'run_seconds': job.get('run_seconds'),
            'gpu': manifest['gpu'], 'render_seconds': manifest['render_seconds'], 'images': manifest['images']}


def run_local(args, params, models, work):
    default_executable = Path('C:/Program Files/Blender Foundation/Blender 5.3/blender.exe')
    executable = args.blender or shutil.which('blender') or default_executable
    output = work / 'result'
    output.mkdir()
    start = time.monotonic()
    for form, model in models.items():
        destination = output / form
        cmd = [str(executable), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '12',
               '--python', str(RUNNER), '--', '--candidate', str(model), '--donor', str(args.donor),
               '--cc0-control', str(args.cc0_control), '--out', str(destination), '--render', 'triage',
               '--neck-head-share', '.35', '--game-hair-shadows', '--resolution', *map(str, params['resolution']),
               '--samples', str(params['samples'])]
        for key, arg in (('cases', '--case'), ('views', '--view'), ('sample_indices', '--sample-index')):
            for value in params[key]:
                cmd.extend((arg, str(value)))
        with (output / f'{form}.log').open('wb') as log:
            status = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        if status.returncode or not (destination / 'motion_report.json').is_file():
            preserved = args.out / f'{form}.log'
            shutil.copyfile(log.name, preserved)
            raise RuntimeError(f'Local Blender review failed ({status.returncode}). See {preserved}')
    return {'backend': 'local', 'images': sum(1 for _ in output.rglob('*.png')),
            'render_seconds': round(time.monotonic() - start, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', type=Path, required=True, help='Directory with the two candidate .blend files.')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--service-url', default=os.environ.get('PBZ_RENDER_SERVICE_URL', 'http://192.168.1.11:8080'))
    parser.add_argument('--mode', choices=('auto', 'remote', 'local'), default='auto')
    parser.add_argument('--blender', default=os.environ.get('PBZ_BLENDER_EXE'))
    parser.add_argument('--donor', type=Path, default=ROOT / 'artifacts/baiqi_cc0_047_rom_donor/Delta_SelfTest.blend')
    parser.add_argument('--cc0-control', type=Path, default=ROOT / 'artifacts/anatomy_base/Base_Female.blend')
    parser.add_argument('--form', action='append', choices=FORMS)
    parser.add_argument('--case', action='append')
    parser.add_argument('--view', action='append', choices=VIEWS)
    parser.add_argument('--sample-index', type=int, action='append')
    parser.add_argument('--resolution', type=int, nargs=2, default=[1280, 1280])
    parser.add_argument('--samples', type=int, default=32)
    parser.add_argument('--timeout', type=int, default=1800, help='Worker render budget in seconds.')
    parser.add_argument('--queue-timeout', type=int, default=60)
    parser.add_argument('--stall-timeout', type=int, default=120)
    args = parser.parse_args()
    args.donor, args.cc0_control, args.out = (path.resolve() for path in (args.donor, args.cc0_control, args.out))
    params = {'forms': args.form or list(FORMS), 'cases': args.case or list(DEFAULT_CASES),
              'views': args.view or ['front', 'oblique'], 'sample_indices': args.sample_index or [0, 2, 4],
              'resolution': args.resolution, 'samples': args.samples, 'engine': 'EEVEE', 'timeout_seconds': args.timeout}
    for key in ('forms', 'cases', 'views', 'sample_indices'):
        if len(set(params[key])) != len(params[key]):
            parser.error(f'Duplicate value in {key}.')
    cases = {case['id']: len(case['samples']) for case in json.loads(SUITE.read_text(encoding='utf-8'))['cases']}
    cases.update(dict.fromkeys(NATIVE_CASES, 5))
    index_min, index_max = min(params['sample_indices']), max(params['sample_indices'])
    if index_min < 0 or any(index_max >= cases.get(name, 0) for name in params['cases']):
        parser.error('Each pose index must exist in every selected case.')
    image_count = 2 * len(params['forms']) * len(params['cases']) * len(params['views']) * len(params['sample_indices'])
    if (len(params['cases']) > 24 or len(params['sample_indices']) > 32 or image_count > 512
            or not all(128 <= side <= 4096 for side in args.resolution) or not 1 <= args.samples <= 128
            or not 30 <= args.timeout <= 14400 or min(args.queue_timeout, args.stall_timeout) <= 0):
        parser.error('Review parameters exceed the unified service limits.')
    models = {form: (args.models / f'BaiQi_CC0_{form}.blend').resolve() for form in params['forms']}
    for path in (*models.values(), args.donor, args.donor.with_name('sampling_report.json'), args.cc0_control):
        if not path.is_file():
            parser.error(f'Missing review input: {path}')
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / 'result').exists():
        parser.error('Output directory already contains a result. Choose a new directory.')
    status, fallback = None, None
    with tempfile.TemporaryDirectory(prefix='.review-', dir=args.out) as staging:
        work = Path(staging)
        if args.mode != 'local':
            try:
                status = run_remote(args, params, models, work)
            except (OSError, RuntimeError, ValueError, KeyError, HTTPException, zipfile.BadZipFile) as error:
                if args.mode == 'remote':
                    raise
                fallback = str(error)
                print(f'Remote review unavailable. Running in local Blender. {fallback}', flush=True)
        if status is None:
            shutil.rmtree(work / 'result', ignore_errors=True)
            status = run_local(args, params, models, work)
            if status['images'] != image_count:
                raise RuntimeError(f'Local Blender produced {status["images"]} images. Expected {image_count}.')
        if status['backend'] == 'remote':
            (work / 'result.zip').replace(args.out / 'result.zip')
        (work / 'result').replace(args.out / 'result')
    status['params'] = params
    status['fallback_reason'] = fallback
    (args.out / 'run.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(status, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
