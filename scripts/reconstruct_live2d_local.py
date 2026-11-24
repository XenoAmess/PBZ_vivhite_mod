"""Generate real 3D geometry from the rendered Delta.zip model, locally.

full.jpg belongs to the separate second model and is intentionally not used.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/Hunyuan3D-2'))
os.environ['HF_HOME'] = str(ROOT / 'tools/models/hf-cache')
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
print('Initializing local CUDA reconstruction libraries', flush=True)
import faulthandler
faulthandler.dump_traceback_later(120, repeat=True)
import torch
from PIL import Image
from transformers.modeling_utils import no_init_weights
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
torch.set_num_threads(min(8, os.cpu_count() or 8))

OUT = ROOT / 'artifacts/live2d_reconstruction'
OUT.mkdir(parents=True, exist_ok=True)
model_dir = ROOT / 'tools/models/hunyuan-mini/hunyuan3d-dit-v2-mini'
started = time.time()
print('Loading local Hunyuan3D mini FP16 weights', flush=True)
with no_init_weights():
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_single_file(
        str(model_dir / 'model.fp16.safetensors'), str(model_dir / 'config.yaml'),
        device='cpu', dtype=torch.float16, use_safetensors=True)
# The upstream standalone pipeline exposes diffusers' offload method without
# defining its components registry. Supply the three real neural components.
pipeline.components = {name: getattr(pipeline, name) for name in ['conditioner','model','vae']}
pipeline._exclude_from_cpu_offload = set()
pipeline.enable_model_cpu_offload(device='cuda')
pipeline.device = torch.device('cuda')
print('Generating shape on RTX 3080 from Live2D only', flush=True)
image = Image.open(OUT / 'input.png').convert('RGBA')
mesh = pipeline(image=image, num_inference_steps=30, guidance_scale=5.5,
                octree_resolution=384, num_chunks=12000,
                generator=torch.Generator(device='cuda').manual_seed(20261124),
                output_type='trimesh', mc_algo='mc')[0]
assert mesh is not None and len(mesh.faces) > 100, 'No usable geometry generated'
mesh.export(OUT / 'Delta_shape.glb')
mesh.export(OUT / 'Delta_shape.ply')
report = {'status': 'shape_generated', 'source': 'Delta.zip', 'reference_used': 'Live2D runtime render',
          'second_model_full_jpg_used': False, 'model': 'tencent/Hunyuan3D-2mini',
          'seed': 20261124, 'steps': 30, 'resolution': 384,
          'vertices': len(mesh.vertices), 'faces': len(mesh.faces),
          'bounds': mesh.bounds.tolist(), 'elapsed_seconds': time.time()-started,
          'limitations': ['Back and sides are inferred from one front view',
                          'Generated topology requires deformation and visual review',
                          'This unrigged geometry is not an installable game mod']}
(OUT / 'shape_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report), flush=True)
