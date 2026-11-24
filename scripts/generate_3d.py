"""Run Microsoft's public TRELLIS.2 image-to-3D demo and retain its mesh.

Uses the supplied reference as input. Requires the public demo to allow an
anonymous session. This script records failures rather than claiming success.
"""
import json
import shutil
import traceback
from pathlib import Path
from gradio_client import Client, handle_file

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'artifacts/reconstruction'
out.mkdir(parents=True, exist_ok=True)
report = {'provider': 'microsoft/TRELLIS.2', 'input': 'resources/full.jpg', 'status': 'started'}
def save():
    (out / 'generation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
save()
try:
    client = Client('microsoft/TRELLIS.2', download_files=str(out), verbose=False)
    print('Session connected', flush=True)
    client.predict(api_name='/start_session')
    image = client.predict(handle_file(str(ROOT / report['input'])), api_name='/preprocess_image')
    print('Image preprocessed', flush=True)
    report['preprocessed'] = str(image)
    save()
    preview = client.predict(image=image, seed=20261124, resolution='1024', api_name='/image_to_3d')
    (out / 'preview.html').write_text(str(preview), encoding='utf-8')
    print('3D inference completed', flush=True)
    models = client.predict(decimation_target=60000, texture_size=2048, api_name='/extract_glb')
    if isinstance(models, str):
        models = [models]
    source = Path(models[0])
    shutil.copy2(source, out / 'Delta_reconstructed.glb')
    report.update(status='mesh_generated', files=[str(p) for p in models])
    print('GLB saved', flush=True)
except Exception as exc:
    report.update(status='failed', error=str(exc), exception=type(exc).__name__)
    print('Reconstruction service failed:', type(exc).__name__, str(exc), flush=True)
finally:
    save()
