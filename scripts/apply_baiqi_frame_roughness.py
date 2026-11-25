"""Update eyewear roughness, nose-pad artwork, or the nose-pad material finish."""
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
from apply_baiqi_eye_glints import pixels


FRAME_MATERIAL = 'BaiQi round gold glasses appearance'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-inputs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--roughness', type=float, default=.46)
    update = parser.add_mutually_exclusive_group()
    update.add_argument('--pad-maps', type=Path, help='Use a local pad color update on the existing finish.')
    update.add_argument('--pad-finish', type=Path, help='Pack the separate nose-pad roughness and metallic channels.')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, inputs, output = ((ROOT / p).resolve() for p in (args.source, args.source_inputs, args.out))
    assert source != output and output.is_relative_to(ROOT)
    assert .36 <= args.roughness <= .58
    expected = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))
    pad_data = None
    if args.pad_maps:
        directory = ROOT / args.pad_maps
        pad_path = directory / 'frame_pads.png'
        pad_data = json.loads((directory / 'frame_pads.json').read_text(encoding='utf-8'))
        assert fingerprint(pad_path) == pad_data['candidate_sha256']
    pad_finish = None
    if args.pad_finish:
        directory = ROOT / args.pad_finish
        mix_path = directory / 'frame_pad_mix.png'
        pad_finish = json.loads((directory / 'frame_pad_mix.json').read_text(encoding='utf-8'))
        assert fingerprint(mix_path) == pad_finish['mix_sha256']
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for form in ('coat_on', 'coat_off'):
        source_path = source / f'BaiQi_CC0_{form}.blend'
        source_hash = fingerprint(source_path)
        assert source_hash == expected[form]['source_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(source_path))
        body, head, rig = (bpy.data.objects[name] for name in ('Body', HEAD, 'Armature'))
        geometry = {obj: mesh_fingerprint(obj) for obj in bpy.context.scene.objects if obj.type == 'MESH'}
        skeleton = rest_signature(rig)
        assert geometry[body] == expected[form]['body_sha256']
        tree = bpy.data.materials[FRAME_MATERIAL].node_tree
        nodes = tree.nodes
        frame = nodes['Principled BSDF']
        assert not frame.inputs['Roughness'].is_linked and not frame.inputs['Metallic'].is_linked
        previous = frame.inputs['Roughness'].default_value
        metal = frame.inputs['Metallic'].default_value
        assert abs(metal - .62) < 1e-6
        if pad_data:
            node = nodes['Image Texture']
            assert pad_data['source_sha256'] == expected[form]['materials'][FRAME_MATERIAL]['images'][0]['sha256']
            replacement = bpy.data.images.load(str(pad_path))
            replacement.colorspace_settings.name = node.image.colorspace_settings.name
            source_rgb, target_rgb = pixels(node.image), pixels(replacement)
            assert source_rgb.shape == target_rgb.shape and np.array_equal(source_rgb[..., 3], target_rgb[..., 3])
            y, x = np.nonzero(np.any(np.abs(source_rgb - target_rgb) > 1e-6, axis=2))
            assert 0 < len(x) and y.min() >= 441 and y.max() <= 469
            assert (((x >= 410) & (x <= 427)) | ((x >= 452) & (x <= 469))).all()
            replacement.pack()
            node.image = replacement
        elif pad_finish:
            assert abs(previous - pad_finish['frame_roughness']) < 1e-6
            assert abs(metal - pad_finish['frame_metallic']) < 1e-6
            assert pad_finish['source_sha256'] == expected[form]['materials'][FRAME_MATERIAL]['images'][0]['sha256']
            albedo = nodes['Image Texture']
            mix = nodes.new('ShaderNodeTexImage')
            mix.label = 'Gold frame and silicone pads'
            mix.image = bpy.data.images.load(str(mix_path))
            mix.image.colorspace_settings.name = 'Non-Color'
            mix.image.pack()
            mix.extension = albedo.extension
            tree.links.new(albedo.inputs['Vector'].links[0].from_socket, mix.inputs['Vector'])
            channels = nodes.new('ShaderNodeSeparateColor')
            tree.links.new(mix.outputs['Color'], channels.inputs['Color'])
            tree.links.new(channels.outputs['Green'], frame.inputs['Roughness'])
            tree.links.new(channels.outputs['Blue'], frame.inputs['Metallic'])
        else:
            assert abs(previous - .36) < 1e-6
            frame.inputs['Roughness'].default_value = args.roughness
        assert all(mesh_fingerprint(obj) == value for obj, value in geometry.items())
        assert rest_signature(rig) == skeleton
        destination = output / source_path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
                        'cc0_body_sha256': geometry[body], 'original_head_sha256': geometry[head],
                        'frame_roughness': frame.inputs['Roughness'].default_value, 'frame_metallic': metal}
        if pad_data:
            report[form]['pad_color'] = pad_data
        if pad_finish:
            report[form]['pad_finish'] = pad_finish
    report_name = 'frame_pads.json' if pad_data else 'frame_finish.json'
    (output / report_name).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
