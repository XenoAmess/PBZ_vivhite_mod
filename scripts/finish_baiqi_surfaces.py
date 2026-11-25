"""Fit the robe and trim on copies of the archived 056 hairstyle candidate."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from fit_baiqi_cc0_wardrobe import rest_signature, smoothstep
from lock_baiqi_cc0_body import mesh_fingerprint
from refine_baiqi_face_lighting import HEAD, fingerprint
from refine_baiqi_hair_finish import CLUMP_PREFIX, ROW_COUNT, ROW_WIDTH


FITTED_TOP = 'BaiQi fitted sleeveless blouse'
COAT = 'BaiQi open coat body'
FRAMES = 'BaiQi round gold glasses'
FRINGE = 'BaiQi bob front'
EXPORT_THICKNESS = 'BaiQi finished edge thickness'


def window(value, lower, peak, upper):
    return smoothstep((value - lower) / (peak - lower)) * smoothstep((upper - value) / (upper - peak))


def shape_bodice(mesh, scale):
    for vertex in mesh.vertices:
        p = vertex.co
        front = smoothstep((p.y - .035) / .055)
        centre = (1 - smoothstep(abs(p.x) / .067))
        # Span the valley between the bust points and relax the cloth under
        # them, with the original collar, side seam and waist as anchors.
        bridge = .014 * centre * window(p.z, 1.104, 1.171, 1.243)
        lower = .006 * (1 - smoothstep(abs(p.x) / .105)) * window(p.z, 1.103, 1.142, 1.179)
        p.y += scale * front * (bridge + lower)
    mesh.update()


def shape_lapel(mesh):
    for vertex in mesh.vertices:
        p = vertex.co
        front = smoothstep((p.y - .04) / .05)
        along = window(p.z, 1.115, 1.237, 1.320)
        # Raise the inside part of the lapel above the shoulder panel.
        across = window(abs(p.x), .041, .076, .146)
        p.y += .005 * front * along * across
    mesh.update()


def shape_hair(obj):
    index = int(obj.name.rsplit(' ', 1)[1])
    phase = index * math.tau / 22
    amount = .0045 * math.sin(4 * phase + .4) + .0025 * math.cos(7 * phase - .4)
    assert len(obj.data.vertices) == ROW_WIDTH * ROW_COUNT
    for vertex in obj.data.vertices:
        travel = (vertex.index // ROW_WIDTH) / (ROW_COUNT - 1)
        tail = smoothstep((travel - .68) / .32)
        vertex.co.z += amount * tail
        vertex.co.x += .0020 * math.sin(3 * phase - .4) * tail
    obj.data.update()


def mark_thickness(obj, thickness):
    modifier = next(modifier for modifier in obj.modifiers if modifier.type == 'SOLIDIFY')
    modifier.name = EXPORT_THICKNESS
    modifier.thickness = thickness
    modifier.offset = -.4


def preview_materials(head, frames):
    for name, fraction in [('BaiQi original face appearance', .43), ('BaiQi neck junction shading', .43)]:
        material = head.data.materials[name]
        finish = next(node for node in material.node_tree.nodes if node.label == 'Skin finish')
        finish.inputs[0].default_value = fraction
    frame = frames.data.materials[0].node_tree.nodes['Principled BSDF']
    frame.inputs['Metallic'].default_value = .62
    frame.inputs['Roughness'].default_value = .36
    for name, roughness in [('BaiQi blouse and collar artwork', .74), ('BaiQi off-white blouse back', .74),
                            ('BaiQi gold-trimmed lapels', .81), ('BaiQi charcoal coat back', .81),
                            ('BaiQi white sleeve cuffs', .66), ('BaiQi navy wrap and source lacing', .61),
                            ('BaiQi navy wrap back', .61)]:
        tree = bpy.data.materials[name].node_tree
        surface = tree.nodes['Principled BSDF']
        surface.inputs['Roughness'].default_value = roughness
        coordinates = tree.nodes.new('ShaderNodeTexCoord')
        yarn = tree.nodes.new('ShaderNodeTexNoise')
        yarn.label = 'Fine cloth weave'
        yarn.inputs['Scale'].default_value = 920.
        yarn.inputs['Detail'].default_value = 1.
        relief = tree.nodes.new('ShaderNodeBump')
        relief.inputs['Strength'].default_value = .18
        relief.inputs['Distance'].default_value = .0003
        tree.links.new(coordinates.outputs['Object'], yarn.inputs['Vector'])
        tree.links.new(yarn.outputs['Fac'], relief.inputs['Height'])
        tree.links.new(relief.outputs['Normal'], surface.inputs['Normal'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'output/live2d_delta/baiqi_056_hair_finish')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bodice-ease', type=float, default=1.)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, output = args.source.resolve(), args.out.resolve()
    assert output != source and output.is_relative_to(ROOT)
    assert .4 <= args.bodice_ease <= 1.1
    pinned = json.loads((source / 'hair_finish.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for form in ('coat_on', 'coat_off'):
        path = source / f'BaiQi_CC0_{form}.blend'
        assert fingerprint(path) == pinned[form]['candidate_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(path))
        objs = bpy.data.objects
        body, head, rig = objs['Body'], objs[HEAD], objs['Armature']
        rest = rest_signature(rig)
        assert mesh_fingerprint(body) == pinned[form]['cc0_body_sha256']
        assert mesh_fingerprint(head) == pinned[form]['original_head_sha256']
        face_atlas = head.data.materials['BaiQi original face appearance'].node_tree.nodes['Image Texture'].image
        face_pixels = bytes(face_atlas.packed_file.data)
        shape_bodice(objs[FITTED_TOP].data, args.bodice_ease)
        shape_lapel(objs[COAT].data)
        for name, thickness in [(FITTED_TOP, .00115), (COAT, .00165), (FRAMES, .00125)]:
            mark_thickness(objs[name], thickness)
        for obj in bpy.context.scene.objects:
            if obj.name.startswith(CLUMP_PREFIX):
                shape_hair(obj)
        for vertex in objs[FRINGE].data.vertices:
            vertex.co.z -= .003 * smoothstep((vertex.co.z - 1.606) / .028)
        objs[FRINGE].data.update()
        preview_materials(head, objs[FRAMES])
        assert mesh_fingerprint(body) == pinned[form]['cc0_body_sha256']
        assert mesh_fingerprint(head) == pinned[form]['original_head_sha256']
        assert bytes(face_atlas.packed_file.data) == face_pixels and rest_signature(rig) == rest
        target = output / path.name
        bpy.ops.wm.save_as_mainfile(filepath=str(target))
        reports[form] = {'source_sha256': fingerprint(path), 'candidate_sha256': fingerprint(target),
                         'cc0_body_sha256': mesh_fingerprint(body), 'original_head_sha256': mesh_fingerprint(head),
                         'bodice_ease': args.bodice_ease}
    (output / 'surface_finish.json').write_text(json.dumps(reports, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
