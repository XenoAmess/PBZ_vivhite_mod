"""Locate the default facial artwork to protect when matching skin pigments."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from baiqi_source_raster import ROOT, SourceRaster


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    output = ROOT / args.out
    output.mkdir(parents=True, exist_ok=True)
    source = SourceRaster(2800, 4400)
    parts = {part['id']: part for part in source.source['parts']}
    protected = {'Eyes'}
    pending = list(protected)
    for part in pending:
        for child in parts[part]['children']:
            if child not in protected:
                protected.add(child)
                pending.append(child)
    crop = (960, 600, 1840, 1400)
    feature = Image.fromarray(source.render(protected)).crop(crop).getchannel('A')
    # The eye shapes and pigment are independent of the skin correction. The
    # mouth and nose are thin artwork on the skin, so their backgrounds follow
    # the skin correction while their source texture and line geometry stay.
    feature = feature.filter(ImageFilter.GaussianBlur(.45))
    feature.save(output / 'protected_facial_art.png')

    face = Image.fromarray(source.render(set(), include_drawables={'Facecolor'})).crop(crop)
    rgba = np.array(face)
    protected_pixels = np.array(feature)
    flat = (rgba[..., 3] > 245) & (protected_pixels < 3)
    rgb, frequency = np.unique(rgba[flat, :3], axis=0, return_counts=True)
    reference = rgb[frequency.argmax()]
    options = np.argwhere(flat & (rgba[..., :3] == reference).all(axis=2))
    assert len(options) > 100
    target = np.array([430., 410.])
    y, x = options[np.argmin(np.linalg.norm(options - target, axis=1))]
    (output / 'protected_facial_art.json').write_text(json.dumps({
        'tile_size': list(feature.size),
        'crop': crop,
        'protected_source_parts': sorted(protected),
        'flat_skin_srgb': reference.tolist(),
        'flat_skin_swatch_uv': [(int(x) + .5) / feature.width, 1 - (int(y) + .5) / feature.height],
    }, indent=2) + '\n', encoding='utf-8')
    source.close()


if __name__ == '__main__':
    main()
