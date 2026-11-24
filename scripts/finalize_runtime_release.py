"""Bundle the exact locally reviewed containers and their visible evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live2d_delta/game_candidate'
MODEL=ROOT/'output/live2d_delta/hunyuan21_polished'
manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
review=json.loads((OUT/'runtime_review.json').read_text(encoding='utf-8'))
assert review['acceptance']=='local_basic_checks_passed'
assert review['tested_files']==manifest['files'],'Runtime evidence belongs to another package'
assert all(review['latest']['tests'][k] is True for k in
           ['save_load','inheritance_save_load','colors','idle','movement','attack','weapon_attachment'])
for name in ['readback.json','cooked_deformation.json']:
    assert json.loads((OUT/name).read_text(encoding='utf-8'))['container_files']==manifest['files']
for item in manifest['files']:
    assert hashlib.sha256((OUT/item['name']).read_bytes()).hexdigest()==item['sha256']
manifest.update(status='runtime_verified_adult_basic',runtime_tested=True,
    user_visual_acceptance=False,runtime_review_file='runtime_review.json',
    scope='adult default, Climax, and Inheritance/MoTian; no young assets')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
shutil.copy2(ROOT/'scripts/install_delta.py',OUT/'install_delta.py')
for name,flag in [('Install',''),('Uninstall',' --uninstall')]:
    (OUT/(name+'.cmd')).write_text('@echo off\r\npy -3 "%~dp0install_delta.py"'+flag+'\r\npause\r\n',encoding='ascii',newline='')
readme='''Delta Live2D 成年魂替换 v0.2

角色只来自 Delta.zip；full.jpg 属于另一份独立模型，没有混用。
少年魂不替换。支持普通成年魂和「传承」外观；同时包含成年Climax身体。
在本机 Steam build 26367565 检查了读档、颜色、待机、移动、挥刀和当前武器挂接。
具体场景、外观和未测范围见 runtime_review.json；Proof 内是本包的实机证据。
这不代表已获用户外观认可，也不代表完整流程、全部武器、其他解锁外观和过场均已验证。

本机已有安装；迁移或重新安装时：关闭游戏后双击 Install.cmd（需要 Python 3）。
卸载：关闭游戏后双击 Uninstall.cmd。脚本只操作三个哈希匹配的本Mod文件。
默认游戏目录：Z:\\SteamLibrary\\steamapps\\common\\PBZ

手动安装：将 z_DeltaLive2D_P.pak / .utoc / .ucas 三个文件放入
游戏目录\\ProjectPBZ\\Content\\Paks\\~mods。
手动卸载：关闭游戏，只移除上述三个 z_DeltaLive2D_P 文件。

手臂已修正肘锚点、外套误绑、锁骨与袖子权重，并重建五指。
背面为推断设计；腕部是重叠接缝，极端姿态的肩肘领口仍可能挤压。
没有新增脸部表情或衣发物理。原游戏程序和原资源包没有被改写。
'''
(OUT/'README.txt').write_text(readme,encoding='utf-8-sig')
files=[f['name'] for f in manifest['files']]+['manifest.json','readback.json',
       'cooked_deformation.json','runtime_review.json','install_delta.py','Install.cmd','Uninstall.cmd','README.txt']
proof=review['latest']['evidence']
archive=ROOT/'output/live2d_delta/Delta_Live2D_Adult_v0.2.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for name in files:
        if name=='manifest.json':
            distribution=dict(manifest);distribution['installed']=False
            bundle.writestr(name,json.dumps(distribution,indent=2))
        else:bundle.write(OUT/name,name)
    bundle.write(ROOT/'output/live2d_delta/Arm_Review.txt','Arm_Review.txt')
    for relative in proof:
        path=(ROOT/relative).resolve();assert path.is_relative_to(ROOT) and path.is_file()
        bundle.write(path,'Proof/'+path.name)
model_archive=ROOT/'output/live2d_delta/Delta_Live2D_3D_v0.2.zip'
with zipfile.ZipFile(model_archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for name in ['Delta_live2d.blend','Delta_live2d.fbx','Delta_live2d.glb','offline_verification.json',
                 'preview_front.png','preview_back.png','preview_side.png','preview_three_quarter.png']:
        bundle.write(MODEL/name,name)
    bundle.write(ROOT/'artifacts/live2d/Delta_projection_padded.png','Textures/Delta_front.png')
    bundle.write(ROOT/'artifacts/live2d/Delta_back_inferred.png','Textures/Delta_back_inferred.png')
    bundle.writestr('README.txt','Delta.zip Live2D reconstruction only. Inferred rear design.\n264 adult Soul bones; 25,609 vertices / 51,084 triangles.\nBlender contains packed textures. This archive is editable model data; install the separate Mod archive in the game.\nNo new facial animation or cloth/hair physics.\n')
for path in [archive,model_archive]:
    with zipfile.ZipFile(path) as bundle:assert bundle.testzip() is None
    print('DELTA_RELEASE',path.name,path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest())
