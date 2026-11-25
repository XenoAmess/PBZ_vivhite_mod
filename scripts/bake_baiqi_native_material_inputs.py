"""Prepare game-native albedo and cutout maps from the approved BaiQi bake."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from shutil import copyfile

import numpy as np
from PIL import Image


# Roughness, specular and metallic values for the adult game's cloth layer.
FRAME_MATERIAL = 'BaiQi round gold glasses appearance'
NECK_MATERIAL = 'BaiQi neck junction shading'
NECK_NORMAL = 'T_BaiQiNative_NeckBridge'
FINISH = {
    'BaiQi original face appearance': (.70, .19, 0.),
    NECK_MATERIAL: (.75, .16, 0.),
    FRAME_MATERIAL: (.34, .27, .62),
    'BaiQi gold': (.37, .27, .62),
    'BaiQi gold_001': (.37, .27, .62),
    'BaiQi bob front appearance': (.64, .19, 0.),
    'BaiQi side hair source color': (.66, .19, 0.),
    'BaiQi black gold headdress appearance': (.71, .15, 0.),
    'BaiQi blouse and collar artwork': (.77, .14, 0.),
    'BaiQi off-white blouse back': (.77, .14, 0.),
    'BaiQi gold-trimmed lapels': (.82, .14, 0.),
    'BaiQi removable coat back': (.82, .14, 0.),
    'BaiQi charcoal coat back': (.82, .14, 0.),
    'BaiQi navy wrap and source lacing': (.61, .23, 0.),
    'BaiQi navy wrap back': (.61, .23, 0.),
    'BaiQi white sleeve cuffs': (.73, .14, 0.),
    'BaiQi pleated skirt artwork': (.79, .14, 0.),
}
WEAVE = {'BaiQi blouse and collar artwork', 'BaiQi off-white blouse back',
         'BaiQi gold-trimmed lapels', 'BaiQi removable coat back', 'BaiQi charcoal coat back',
         'BaiQi navy wrap and source lacing', 'BaiQi navy wrap back', 'BaiQi white sleeve cuffs'}


def srgb_channel(linear):
    return round(255 * (12.92 * linear if linear <= .0031308 else 1.055 * linear ** (1 / 2.4) - .055))


def texture_size(image):
    return tuple(2 ** round(math.log2(value)) for value in image.size)


def weave_texture(directory):
    y, x = np.mgrid[0:512, 0:512] * (math.tau / 512)
    warp = np.cos(73 * x + .45 * np.sin(69 * y))
    weft = np.cos(69 * y - .45 * np.sin(73 * x))
    normal = np.stack((.16 * warp, .12 * weft, np.sqrt(1 - (.16 * warp) ** 2 - (.12 * weft) ** 2)), axis=-1)
    name = 'T_BaiQiNative_ClothWeave'
    Image.fromarray(np.rint((normal * .5 + .5) * 255).astype(np.uint8)).save(directory / f'{name}.png')
    return name


def face_mix_texture(mask_path, roughness):
    with Image.open(mask_path) as protected:
        opacity = np.asarray(protected.convert('L').resize(texture_size(protected), Image.Resampling.LANCZOS)) / 255
    graded = (roughness * (1 - opacity) + .48 * opacity) * 255
    channels = np.stack((np.full_like(graded, 255), graded, np.zeros_like(graded)), axis=-1)
    return Image.fromarray(np.rint(channels).astype(np.uint8))


def surface_finish(inputs, directory, materials, *, frame_roughness=None, neck_normal=None):
    source = json.loads((inputs / 'form_inputs.json').read_text(encoding='utf-8'))['coat_on']['materials']
    weave = weave_texture(directory)
    profiles = {}
    for name, (roughness, specular, metallic) in FINISH.items():
        if name not in materials:
            continue
        assert materials[name]['type'] not in {'hidden', 'masked', 'skin_body'}, name
        if name == FRAME_MATERIAL and frame_roughness is not None:
            roughness = frame_roughness
        stem = hashlib.sha256(name.encode()).hexdigest()[:14]
        mix = 'T_BaiQiMix_' + stem
        if materials[name]['type'] == 'skin_face':
            mask = next(row for row in source[name]['images'] if row['label'] == 'Keep original facial artwork')
            image = face_mix_texture(inputs / mask['path'], roughness)
        else:
            image = Image.new('RGB', (64, 64), (255, round(255 * roughness), round(255 * metallic)))
        image.save(directory / f'{mix}.png')
        profiles[name] = {'mix': mix, 'specular': specular, 'roughness': roughness, 'metallic': metallic}
        if name in WEAVE:
            profiles[name].update(normal=weave, normal_strength=.32)
    if neck_normal:
        with Image.open(neck_normal) as normal:
            assert normal.mode == 'RGB' and normal.size == (512, 512), neck_normal
        copyfile(neck_normal, directory / f'{NECK_NORMAL}.png')
        profiles[NECK_MATERIAL].update(normal=NECK_NORMAL, normal_strength=.70)
    (inputs / 'surface_finish.json').write_text(json.dumps(profiles, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', type=Path)
    parser.add_argument('skin_report', type=Path)
    parser.add_argument('--surface-finish', action='store_true', help='Bake separate roughness and normal profiles.')
    parser.add_argument('--frame-roughness', type=float, help='Roughness of the gold eyewear frame only.')
    parser.add_argument('--neck-normal', type=Path, help='Bake the approved bridge map into its native material only.')
    args = parser.parse_args()
    if args.frame_roughness is not None:
        assert args.surface_finish and .36 <= args.frame_roughness <= .58
    if args.neck_normal and not args.surface_finish:
        parser.error('--neck-normal requires --surface-finish')
    directory = args.inputs / 'native_textures'
    directory.mkdir(exist_ok=True)
    materials = json.loads((args.inputs / 'engine_materials.json').read_text(encoding='utf-8'))
    arm = json.loads(args.skin_report.read_text(encoding='utf-8'))['coat_off']['arm_reference_texel']
    for name, row in materials.items():
        stem = hashlib.sha256(name.encode()).hexdigest()[:14]
        kind = row['type']
        if row['texture']:
            with Image.open(args.inputs / row['texture']) as image:
                color = image.convert('RGBA').resize(texture_size(image), Image.Resampling.LANCZOS)
        else:
            rgb = [round(channel * 255) for channel in arm] if kind == 'skin_junction' else [
                srgb_channel(channel) for channel in row['color'][:3]]
            color = Image.new('RGBA', (64, 64), (*rgb, 0 if kind == 'hidden' else 255))
        color.convert('RGB').save(directory / f'T_BaiQiNative_{stem}.png')
        if kind in {'masked', 'hidden'}:
            color.getchannel('A').convert('RGB').save(directory / f'T_BaiQiAlpha_{stem}.png')
    for name, flat in [('FlatNormal', (128, 128, 255)), ('Mix', (255, 195, 0)),
                       ('NeutralBlack', (0, 0, 0)), ('NeutralWhite', (255, 255, 255))]:
        Image.new('RGB', (64, 64), flat).save(directory / f'T_BaiQiNative_{name}.png')
    if args.surface_finish:
        surface_finish(args.inputs, directory, materials, frame_roughness=args.frame_roughness,
                       neck_normal=args.neck_normal)


if __name__ == '__main__':
    main()
