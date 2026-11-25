"""Apply artwork corrections to the existing BaiQi face and eye states."""
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


def coverage(poses, state, kind):
    image = bpy.data.images.load(str(poses / f'{state}_{kind}.png'))
    image.colorspace_settings.name = 'Non-Color'
    assert tuple(image.size) == (880, 800)
    pixels_read = pixels(image)[..., 0]
    bpy.data.images.remove(image)
    return pixels_read


def replace(poses, state, node, correction_name):
    original = node.image
    new = bpy.data.images.load(str(poses / f'{state}.png'))
    assert tuple(new.size) == tuple(original.size) == (880, 800)
    new.colorspace_settings.name = original.colorspace_settings.name
    source, result = pixels(original), pixels(new)
    changed = np.any(np.abs(source - result) > 1e-6, axis=2)
    y, x = np.nonzero(changed)
    coverage_kind = {'iris_pigment': 'iris', 'lower_iris_tone': 'iris', 'sclera_depth': 'sclera'}.get(correction_name)
    if coverage_kind:
        mask = coverage(poses, state, coverage_kind) > 0.
        assert np.array_equal(source[..., 3], result[..., 3]), state
        assert not (changed & ~mask).any() and bool(len(x)) == (state != 'closed'), state
        if coverage_kind == 'sclera':
            assert not (changed & (coverage(poses, state, 'iris') >= 249.5 / 255.)).any(), state
    if correction_name == 'nose_registration':
        assert len(x) and np.array_equal(source[..., 3], result[..., 3]), state
        assert 398 <= x.min() <= x.max() <= 467 and 440 <= y.min() <= y.max() <= 511, state
    if correction_name in {'jaw_outline', 'underjaw_tint', 'underjaw_edge'}:
        guide = bpy.data.images.load(str(poses / f'{correction_name}_mask.png'))
        guide.colorspace_settings.name = 'Non-Color'
        region = pixels(guide)[..., 0] > 0.
        bpy.data.images.remove(guide)
        assert len(x) and not (changed & ~region).any(), state
        if correction_name == 'jaw_outline':
            assert 280 <= x.min() <= x.max() <= 600 and 492 <= y.min() <= y.max() <= 612, state
        elif correction_name == 'underjaw_tint':
            assert np.array_equal(source[..., 3], result[..., 3]), state
            assert 380 <= x.min() <= x.max() <= 450 and 572 <= y.min() <= y.max() <= 620, state
        else:
            assert np.array_equal(source[..., 3], result[..., 3]), state
            assert 340 <= x.min() <= x.max() <= 460 and 544 <= y.min() <= y.max() <= 621, state
    if not len(x):
        bpy.data.images.remove(new)
        return {'changed_pixels': 0, 'bounds': None}
    min_y = 375 if coverage_kind else 412
    if correction_name not in {'nose_registration', 'jaw_outline', 'underjaw_tint', 'underjaw_edge'}:
        assert int(x.min()) >= 280 and int(x.max()) <= 600 and int(y.min()) >= min_y and int(y.max()) <= 465, state
    new.pack()
    node.image = new
    return {'changed_pixels': int(changed.sum()), 'bounds': [int(x.min()), int(y.min()), int(x.max()), int(y.max())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    area = parser.add_mutually_exclusive_group()
    area.add_argument('--iris-only', action='store_true', help='Require unchanged pixels outside original iris coverage.')
    area.add_argument('--sclera-only', action='store_true', help='Require unchanged pixels outside original eye-white coverage.')
    area.add_argument('--nose-registration', action='store_true', help='Verify a local nose paint correction.')
    area.add_argument('--lower-iris-tone', action='store_true', help='Verify the limited lower iris pigment correction.')
    area.add_argument('--jaw-outline', action='store_true', help='Verify the original lower jaw contour adjustment.')
    area.add_argument('--underjaw-tint', action='store_true', help='Verify the painted underjaw tint adjustment.')
    area.add_argument('--underjaw-edge', action='store_true', help='Verify the underjaw edge color adjustment.')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, poses, output = ((ROOT / p).resolve() for p in (args.source, args.source_inputs, args.poses, args.out))
    assert source != output and output.is_relative_to(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    glint_path = poses / 'glint.json'
    glint = None
    if not args.nose_registration or glint_path.is_file():
        glint = json.loads(glint_path.read_text(encoding='utf-8'))
        assert set(glint['drawables']) == {'ArtMesh85', 'ArtMesh94'}
    selected = ((args.iris_only, 'iris_pigment', {'ArtMesh88', 'ArtMesh103'}),
                (args.lower_iris_tone, 'lower_iris_tone', {'ArtMesh88', 'ArtMesh103'}),
                (args.sclera_only, 'sclera_depth', {'ArtMesh90', 'ArtMesh93'}),
                (args.nose_registration, 'nose_registration', {'Nose2', 'ArtMesh106'}),
                (args.jaw_outline, 'jaw_outline', {'ArtMesh116'}),
                (args.underjaw_tint, 'underjaw_tint', {'ArtMesh115', 'ArtMesh233'}),
                (args.underjaw_edge, 'underjaw_edge', {'ArtMesh54'}))
    correction_name, drawables = next(((name, drawables) for active, name, drawables in selected if active),
                                      ('eye_glints', None))
    correction = None
    if drawables:
        correction = json.loads((poses / f'{correction_name}.json').read_text(encoding='utf-8'))
        assert set(correction['drawables']) == drawables
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
        changed = {state: replace(poses, state, states[state], correction_name) for state in STATES}
        assert changed['neutral']['changed_pixels'] > 0
        assert all(mesh_fingerprint(obj) == value for obj, value in geometry.items())
        assert rest_signature(rig) == skeleton
        destination = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': geometry[body], 'original_head_sha256': geometry[head],
                        'states': changed}
        if glint:
            report[form]['opacity_scale'] = glint['opacity_scale']
        if correction:
            report[form][correction_name] = correction
    (output / f'{correction_name}.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
