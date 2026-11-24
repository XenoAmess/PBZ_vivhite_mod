"""Bundle a local test build with independent installation and removal scripts."""
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/live2d_delta/game_candidate'
manifest=json.loads((OUT/'manifest.json').read_text())
assert manifest['status']=='readback_verified_pending_game'
assert json.loads((OUT/'cooked_deformation.json').read_text())['status']=='cooked_geometry_and_pose_check'
shutil.copy2(ROOT/'scripts/install_delta.py',OUT/'install_delta.py')
for name,flag in [('Install',''),('Uninstall',' --uninstall')]:
    (OUT/(name+'.cmd')).write_text('@echo off\r\npy -3 "%~dp0install_delta.py"'+flag+'\r\npause\r\n',encoding='ascii',newline='')
readme='''Delta Live2D 成年魂手臂修正测试版

仅使用 Delta.zip 对应角色。full.jpg 的角色是另一份模型，本包未使用。
替换普通成年魂和成年 Climax；少年魂不变，其他解锁服装暂未覆盖。

自动安装：游戏关闭后双击 Install.cmd（需要本机 Python 3）。
自动卸载：游戏关闭后双击 Uninstall.cmd。脚本只处理本包三个校验通过的文件。
默认游戏位置：Z:\\SteamLibrary\\steamapps\\common\\PBZ

手动安装：将 z_DeltaLive2D_P.pak / .utoc / .ucas 三个文件放入
游戏目录\\ProjectPBZ\\Content\\Paks\\~mods。
手动卸载：关闭游戏，仅删除上面三个 z_DeltaLive2D_P 文件。

手臂修正：上移肘部拟合锚点、补入原版扭转骨蒙皮、独立拟合手掌方向、
重建五指和关节边环，并采用16位蒙皮权重减少烘焙误差。

已完成：264骨参考变换、18材质槽、资源包读回、实际游戏动作离线形变比较。
尚未完成：游戏内持武器/IK/后处理实测，肩肘袖口细修、侧背贴图和整体外形精修。
没有新脸部表情或衣发物理。这是粗模测试包，不是完成视觉验收的成品。
本包不启动游戏，不改写游戏程序或原始资源包。
'''
(OUT/'README.txt').write_text(readme,encoding='utf-8-sig')
files=[f['name'] for f in manifest['files']]+['manifest.json','readback.json','cooked_deformation.json',
        'install_delta.py','Install.cmd','Uninstall.cmd','README.txt']
archive=ROOT/'output/live2d_delta/Delta_Live2D_Adult_ArmFix_Test.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
    for name in files:
        if name=='manifest.json':
            distribution=dict(manifest);distribution['installed']=False
            bundle.writestr(name,json.dumps(distribution,indent=2))
        else:bundle.write(OUT/name,name)
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    assert set(bundle.namelist())==set(files)
print('DELTA_TEST_ARCHIVE',archive,archive.stat().st_size)
