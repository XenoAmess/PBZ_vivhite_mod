"""Layer source iris roughness into the five existing Unreal material maps."""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from bake_baiqi_eye_materials import load, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--roughness', type=float, default=.37)
    args = parser.parse_args()
    assert .25 <= args.roughness <= .47
    palette = load(args.inputs / 'eye_palette.json')
    finishes = load(args.inputs / 'surface_finish.json')
    native = args.inputs / 'native_textures'
    states = {'neutral': palette['neutral'], **{name: row['material'] for name, row in palette['states'].items()}}
    report = {'roughness': args.roughness, 'states': {}}
    bounds = palette['affected_bounds']
    for name, material in states.items():
        path = native / f'{finishes[material]["mix"]}.png'
        with Image.open(path) as image, Image.open(args.poses / f'{name}_iris.png') as mask:
            source = np.asarray(image.convert('RGB'))
            assert mask.mode == 'L' and mask.size == (880, 800)
            alpha = np.asarray(mask.resize(image.size, Image.Resampling.BILINEAR), dtype=np.float32) / 255.
        x0, y0, x1, y1 = bounds
        panel = alpha[y0:y1, x0:x1]
        assert np.count_nonzero(alpha) == np.count_nonzero(panel), name
        count = int(np.count_nonzero(alpha))
        assert bool(count) == (name != 'closed'), name
        toned = source.copy()
        if count:
            roughness = source[..., 1] * (1. - alpha) + (255. * args.roughness) * alpha
            toned[..., 1] = np.rint(roughness).astype(np.uint8)
            Image.fromarray(toned).save(path)
        changed = int(np.count_nonzero(source[..., 1] != toned[..., 1]))
        report['states'][name] = {'mix': path.name, 'coverage_pixels': count, 'changed_roughness_pixels': changed}
    save(args.inputs / 'iris_roughness.json', report)
    print('BAIQI_IRIS_ROUGHNESS', report, flush=True)


if __name__ == '__main__':
    main()
