"""Use softer source eye glints on the existing BaiQi face and eye states."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint


FACE = 'BaiQi original face appearance'
STATES = ('neutral', 'half_blink', 'closed', 'look_left', 'look_right')


def pixels(image):
    data = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(data)
    return data.reshape(image.size[1], image.size[0], 4)[::-1]


def replace(poses, state, node):
    original = node.image
    new = bpy.data.images.load(str(poses / f'{state}.png'))
    assert tuple(new.size) == tuple(original.size) == (880, 800)
    new.colorspace_settings.name = original.colorspace_settings.name
    changed = np.any(np.abs(pixels(original) - pixels(new)) > 1e-6, axis=2)
    y, x = np.nonzero(changed)
    if not len(x):
        bpy.data.images.remove(new)
        return {'changed_pixels': 0, 'bounds': None}
    assert int(x.min()) >= 280 and int(x.max()) <= 600 and int(y.min()) >= 412 and int(y.max()) <= 465, state
    new.pack()
    node.image = new
    return {'changed_pixels': int(changed.sum()), 'bounds': [int(x.min()), int(y.min()), int(x.max()), int(y.max())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, poses, output = ((ROOT / p).resolve() for p in (args.source, args.source_inputs, args.poses, args.out))
    assert source != output and output.is_relative_to(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    glint = json.loads((poses / 'glint.json').read_text(encoding='utf-8'))
    assert set(glint['drawables']) == {'ArtMesh85', 'ArtMesh94'}
    report = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        body, head, rig = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        geometry = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        assert geometry[body] == expected[form]['body_sha256']
        skeleton = rest_signature(rig)
        tree = head.data.materials[FACE].node_tree
        states = {'neutral': tree.nodes['Image Texture']}
        states.update({node.label: node for node in tree.nodes
                       if node.type == 'TEX_IMAGE' and node.label in STATES[1:]})
        assert set(states) == set(STATES)
        changed = {state: replace(poses, state, states[state]) for state in STATES}
        assert changed['neutral']['changed_pixels'] > 0
        assert all(mesh_fingerprint(obj) == value for obj, value in geometry.items())
        assert rest_signature(rig) == skeleton
        destination = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': geometry[body], 'original_head_sha256': geometry[head],
                        'opacity_scale': glint['opacity_scale'], 'states': changed}
    (output / 'eye_glints.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
