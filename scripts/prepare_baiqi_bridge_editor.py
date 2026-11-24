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
        source = source.rstrip() + '\n\n' + include + '\n'
    original = 'if (!Instance || !Instance->GetOutermost()->GetName().StartsWith(TEXT("/HuaShira/Mods/DeltaLive2D/Materials/"))) return;'
    native_materials = '''if (!Instance) return;
        const FString PackageName = Instance->GetOutermost()->GetName();
        const bool bBaiQi = PackageName.StartsWith(TEXT("/HuaShira/Mods/BaiQi054/Shared/Native/Materials/"));
        if (!bBaiQi && !PackageName.StartsWith(TEXT("/HuaShira/Mods/DeltaLive2D/Materials/"))) return;
        const bool bHair = bBaiQi && Instance->Parent && Instance->Parent->GetName() == TEXT("MI_ZeroHun_HairCard_Health");'''
    if original in source:
        source = source.replace(original, native_materials)
        source = source.replace('Cached.ParentLayerIndexRemap = {0, 1};',
                                'Cached.ParentLayerIndexRemap = {0, bHair ? INDEX_NONE : 1};')
    assert 'const bool bBaiQi' in source
    body.write_text(source, encoding='utf-8')
    shutil.copyfile(ROOT / 'scripts/baiqi_bridge_animgraph.inl', private / 'baiqi_bridge_animgraph.inl')


if __name__ == '__main__':
    main()
