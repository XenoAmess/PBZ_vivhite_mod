"""Expose the BaiQi graph authoring helper through the existing UE editor plugin."""
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'build/UE/ProjectPBZ/Plugins/PBZModTools/Source/PBZModTools'


def main():
    private = SOURCE / 'Private'
    declaration = SOURCE / 'Public/PBZModToolsLibrary.h'
    body = private / 'PBZModToolsLibrary.cpp'
    assert declaration.is_file() and body.is_file()
    header = declaration.read_text(encoding='utf-8-sig')
    signatures = [
        'BuildBaiQiBridgeGraph(UAnimBlueprint* Blueprint, const FString& Spec)',
        'SampleBaiQiBridgePose(USkeletalMesh* Mesh, UAnimSequence* Animation, float Fraction)',
    ]
    additions = ''.join('\tUFUNCTION(BlueprintCallable, Category = "PBZModTools")\n'
                        f'\tstatic FString {signature};\n\n' for signature in signatures if signature not in header)
    if additions:
        marker = 'public:\n'
        assert header.count(marker) == 1
        declaration.write_text(header.replace(marker, marker + additions), encoding='utf-8')
    source = body.read_text(encoding='utf-8-sig')
    include = '#include "baiqi_bridge_animgraph.inl"'
    if include not in source:
        body.write_text(source.rstrip() + '\n\n' + include + '\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'scripts/baiqi_bridge_animgraph.inl', private / 'baiqi_bridge_animgraph.inl')


if __name__ == '__main__':
    main()
