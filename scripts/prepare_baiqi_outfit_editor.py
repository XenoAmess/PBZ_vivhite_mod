"""Set up editor-only authoring for the supported PBZ Outfit Framework schemas."""
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'build/UE/ProjectPBZ'


def main():
    module = PROJECT / 'Source/ProjectPBZ'
    module.mkdir(parents=True, exist_ok=True)
    description = PROJECT / 'ProjectPBZ.uproject'
    data = json.loads(description.read_text(encoding='utf-8-sig'))
    data['Modules'] = [{'Name': 'ProjectPBZ', 'Type': 'Runtime', 'LoadingPhase': 'Default'}]
    plugins = data['Plugins']
    if not any(plugin['Name'] == 'PBZModLoader' for plugin in plugins):
        plugins.append({'Name': 'PBZModLoader', 'Enabled': True})
    description.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    plugin = PROJECT / 'Plugins/PBZModLoader'
    (plugin / 'Content').mkdir(parents=True, exist_ok=True)
    (plugin / 'PBZModLoader.uplugin').write_text(
        json.dumps({'FileVersion': 3, 'Version': 1, 'FriendlyName': 'PBZModLoader authoring schema',
                    'CanContainContent': True}) + '\n', encoding='utf-8')
    for name in ('ProjectPBZ.Target.cs', 'ProjectPBZEditor.Target.cs'):
        target = PROJECT / 'Source' / name
        if not target.exists():
            class_name = name.removesuffix('.Target.cs')
            target_type = 'Editor' if class_name.endswith('Editor') else 'Game'
            target.write_text(f'''using UnrealBuildTool;
public class {class_name}Target : TargetRules
{{
    public {class_name}Target(TargetInfo Target) : base(Target)
    {{
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        Type = TargetType.{target_type};
        ExtraModuleNames.Add("ProjectPBZ");
    }}
}}
''', encoding='utf-8')
    (module / 'ProjectPBZ.Build.cs').write_text('''using UnrealBuildTool;
public class ProjectPBZ : ModuleRules
{
    public ProjectPBZ(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
    }
}
''', encoding='utf-8')
    (module / 'ProjectPBZ.cpp').write_text('#include "Modules/ModuleManager.h"\n'
                                         'IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, ProjectPBZ, "ProjectPBZ");\n',
                                         encoding='utf-8')
    shutil.copyfile(ROOT / 'scripts/baiqi_appearance_schema.h', module / 'baiqi_appearance_schema.h')
    tooling = PROJECT / 'Plugins/PBZModTools/Source/PBZModTools'
    header = tooling / 'Public/PBZModToolsLibrary.h'
    signature = 'static FString BuildBaiQiOutfitTables(const FString& Spec);'
    text = header.read_text(encoding='utf-8-sig')
    if signature not in text:
        header.write_text(text.replace('public:\n', 'public:\n\tUFUNCTION(BlueprintCallable, Category = "PBZModTools")\n'
                                       f'\t{signature}\n\n', 1), encoding='utf-8')
    source = tooling / 'Private/PBZModToolsLibrary.cpp'
    include = '#include "baiqi_outfit_tables.inl"'
    text = source.read_text(encoding='utf-8-sig')
    if include not in text:
        source.write_text(text.rstrip() + '\n\n' + include + '\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'scripts/baiqi_outfit_tables.inl', tooling / 'Private/baiqi_outfit_tables.inl')
    config = PROJECT / 'Config/DefaultGame.ini'
    text = config.read_text(encoding='utf-8-sig')
    cook_path = '+DirectoriesToAlwaysCook=(Path="/Game/Mods/PBZOutfitSlots")'
    section = '[/Script/UnrealEd.ProjectPackagingSettings]\n'
    if cook_path not in text:
        assert section in text
        config.write_text(text.replace(section, section + cook_path + '\n', 1), encoding='utf-8')


if __name__ == '__main__':
    main()
