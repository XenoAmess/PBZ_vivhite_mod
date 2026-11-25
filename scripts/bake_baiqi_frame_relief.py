"""Give the original gold rims a rounded tangent normal without changing their color."""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from bake_baiqi_eye_materials import load, save
from bake_baiqi_face_relief import encode
from bake_baiqi_native_material_inputs import FRAME_MATERIAL, texture_size


NORMAL = 'T_BaiQiNative_FrameRelief'
STRENGTH = .65
MAX_DISTANCE = 8


def inside_distance(mask):
    distance = np.full(mask.shape, MAX_DISTANCE, dtype=np.float32)
    padded = np.pad(mask, MAX_DISTANCE, mode='constant')
    height, width = mask.shape
    for row in range(-MAX_DISTANCE, MAX_DISTANCE + 1):
        for column in range(-MAX_DISTANCE, MAX_DISTANCE + 1):
            reach = np.hypot(row, column)
            if reach <= MAX_DISTANCE:
                y, x = MAX_DISTANCE + row, MAX_DISTANCE + column
                outside = ~padded[y:y + height, x:x + width]
                distance[outside] = np.minimum(distance[outside], reach)
    return distance


def rim_normals(source):
    alpha = np.asarray(source.convert('RGBA'))[..., 3]
    mask = Image.fromarray(np.uint8(alpha >= 128) * 255)
    mask = np.asarray(mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))) > 0
    rows, columns = np.nonzero(mask)
    rim_area = (slice(rows.min() - 4, rows.max() + 5), slice(columns.min() - 4, columns.max() + 5))
    distance = inside_distance(mask[rim_area])
    height = np.zeros(mask.shape, dtype=np.float32)
    height[rim_area] = np.sin(np.clip((distance - .5) / 3.6, 0., 1.) * (.5 * np.pi))
    y, x = np.indices(mask.shape)
    # Exclude the original bridge and give the 073 nose pads a small buffer.
    metal_rims = ((x < 418) | (x > 463))
    pads = (((x >= 406) & (x <= 431)) | ((x >= 448) & (x <= 473))) & (y >= 437) & (y <= 473)
    height *= metal_rims & ~pads
    softened = Image.fromarray(np.rint(height * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.76))
    dy, dx = np.gradient(np.asarray(softened, dtype=np.float32) / 255.)
    limit = np.maximum(1., np.hypot(dx, dy) / .22)
    assert np.any(dx) and np.any(dy)
    pads = (((x >= 410) & (x <= 427)) | ((x >= 452) & (x <= 469))) & (y >= 441) & (y <= 469)
    assert not np.any(dx[pads]) and not np.any(dy[pads])
    return -dx / limit, dy / limit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--attach-native', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    forms = load(args.inputs / 'form_inputs.json')
    source = forms['coat_on']['materials'][FRAME_MATERIAL]
    assert source == forms['coat_off']['materials'][FRAME_MATERIAL]
    albedo = next(row for row in source['images'] if row['node'] == 'Image Texture')
    path = args.inputs / albedo['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == albedo['sha256']
    with Image.open(path) as image:
        assert image.size == (880, 800)
        nx, ny = rim_normals(image)
        size = texture_size(image)
    blender = args.out / 'frame_relief_blender.png'
    encode(nx, ny).save(blender)
    report = {'source_sha256': albedo['sha256'], 'normal_strength': STRENGTH,
              'tilt_degrees': float(np.degrees(np.arctan(np.hypot(nx, ny).max()))),
              'blender_sha256': hashlib.sha256(blender.read_bytes()).hexdigest()}
    if args.attach_native:
        finish_path = args.inputs / 'surface_finish.json'
        finishes = load(finish_path)
        output = args.inputs / 'native_textures' / f'{NORMAL}.png'
        encode(nx, -ny).resize(size, Image.Resampling.BILINEAR).save(output)
        finishes[FRAME_MATERIAL].update(normal=NORMAL, normal_strength=STRENGTH)
        save(finish_path, finishes)
        report['native_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    save(args.out / 'frame_relief_inputs.json', report)


if __name__ == '__main__':
    main()
