"""Test a softly lit skin finish on copies of the preserved BaiQi 054 forms."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lock_baiqi_cc0_body import mesh_fingerprint


HEAD = 'BaiQi restored authored head and face'
SKIN_LABEL = 'Shared arm pigment with the original colored lines and soft con'
JUNCTION_LABEL = 'Same arm pigment on the sides of the face and neck transition'


def add_diffuse_response(material, emission, color, fraction):
    tree = material.node_tree
    links = list(emission.outputs[0].links)
    assert len(links) == 1
    outgoing = links[0].to_socket
    diffuse = tree.nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.label = 'Diffuse skin response'
    diffuse.inputs['Roughness'].default_value = .55
    tree.links.new(color, diffuse.inputs['Color'])
    blend = tree.nodes.new('ShaderNodeMixShader')
    blend.label = 'Skin finish'
    blend.inputs[0].default_value = fraction
    tree.links.new(emission.outputs[0], blend.inputs[1])
    tree.links.new(diffuse.outputs[0], blend.inputs[2])
    tree.links.new(blend.outputs[0], outgoing)


def fingerprint(path):
    with path.open('rb') as data:
        return hashlib.file_digest(data, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'output/live2d_delta/baiqi_cc0_054')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--diffuse-fraction', type=float, default=.28)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    assert 0 < args.diffuse_fraction < 1
    source = args.source.resolve()
    out = args.out.resolve()
    assert out != source and out.is_relative_to(ROOT)
    out.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((ROOT / 'repro/baselines/baiqi_054.json').read_text(encoding='utf-8'))
    pinned = {row['name']: row['sha256'] for row in baseline['files']}
    report = {}
    for form in ('coat_on', 'coat_off'):
        filename = f'BaiQi_CC0_{form}.blend'
        base_path = source / filename
        source_hash = fingerprint(base_path)
        assert source_hash == pinned[filename]
        bpy.ops.wm.open_mainfile(filepath=str(base_path))
        body = bpy.data.objects['Body']
        head = bpy.data.objects[HEAD]
        body_hash = mesh_fingerprint(body)
        head_hash = mesh_fingerprint(head)
        assert body_hash == body['baiqi_cc0_geometry_sha256'] == baseline['protected_cc0_body_sha256']
        face = head.data.materials['BaiQi original face appearance']
        collar = head.data.materials['BaiQi neck junction shading']
        atlas = face.node_tree.nodes['Image Texture'].image
        atlas_hash = hashlib.sha256(atlas.packed_file.data).hexdigest()
        skin = next(node for node in face.node_tree.nodes if node.type == 'EMISSION' and node.label.startswith(SKIN_LABEL))
        neck = next(node for node in collar.node_tree.nodes if node.type == 'EMISSION' and node.label == JUNCTION_LABEL)
        contour = skin.inputs['Color'].links[0].from_node
        pigment = contour.inputs[0].links[0].from_socket
        add_diffuse_response(face, skin, pigment, args.diffuse_fraction)
        add_diffuse_response(collar, neck, neck.inputs['Color'].links[0].from_socket, args.diffuse_fraction)
        assert mesh_fingerprint(body) == body_hash and mesh_fingerprint(head) == head_hash
        assert hashlib.sha256(atlas.packed_file.data).hexdigest() == atlas_hash
        destination = out / filename
        bpy.ops.wm.save_as_mainfile(filepath=str(destination))
        report[form] = {
            'source_sha256': source_hash, 'candidate_sha256': fingerprint(destination),
            'cc0_body_sha256': body_hash, 'authored_head_mesh_sha256': head_hash,
            'authored_face_atlas_sha256': atlas_hash, 'diffuse_fraction': args.diffuse_fraction,
        }
    (out / 'face_lighting.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('BAIQI_FACE_CANDIDATE', out, flush=True)


if __name__ == '__main__':
    main()
