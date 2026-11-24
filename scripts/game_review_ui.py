"""Inspect/control only this game's window during the local runtime review."""
import ctypes
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time
import win32gui
import win32con
import win32process
import pyautogui
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parents[1]
ctypes.windll.shcore.SetProcessDpiAwareness(2)
query="@(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*PBZ*' } | Select-Object ProcessId,ExecutablePath) | ConvertTo-Json -Compress"
result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',query],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
processes=json.loads(result.stdout or '[]')
if isinstance(processes,dict):processes=[processes]
game=Path(r'Z:\SteamLibrary\steamapps\common\PBZ').resolve()
pids={p['ProcessId'] for p in processes if p.get('ExecutablePath') and Path(p['ExecutablePath']).resolve().is_relative_to(game)}
windows=[]
def visit(hwnd,_):
    _,pid=win32process.GetWindowThreadProcessId(hwnd)
    if pid not in pids or not win32gui.IsWindowVisible(hwnd):return
    x0,y0,x1,y1=win32gui.GetWindowRect(hwnd)
    if x1-x0>600 and y1-y0>350:windows.append((hwnd,pid,win32gui.GetWindowText(hwnd),win32gui.GetClassName(hwnd)))
win32gui.EnumWindows(visit,None)
action=sys.argv[1] if len(sys.argv)>1 else 'list'
if action=='list':print(json.dumps({'pids':sorted(pids),'windows':windows},ensure_ascii=False));raise SystemExit(0)
assert windows,'No visible PBZ game window'
windows.sort(key=lambda row:('Unreal' in row[3],bool(row[2])),reverse=True)
hwnd,pid,title=windows[0][:3]
if win32gui.IsIconic(hwnd):win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
if win32gui.GetForegroundWindow()!=hwnd and '--passive' not in sys.argv:
    user32=ctypes.windll.user32
    current=ctypes.windll.kernel32.GetCurrentThreadId()
    foreground=win32gui.GetForegroundWindow()
    foreground_thread,_=win32process.GetWindowThreadProcessId(foreground)
    attached=bool(user32.AttachThreadInput(current,foreground_thread,True))
    try:
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    finally:
        if attached:user32.AttachThreadInput(current,foreground_thread,False)
    time.sleep(.3)
assert action=='shot' or win32gui.GetForegroundWindow()==hwnd,'Game must be foreground for this scoped review'
rect=win32gui.GetWindowRect(hwnd)
if action=='key':
    count=int(sys.argv[3]) if len(sys.argv)>3 else 1;assert 1<=count<=6
    for _ in range(count):
        pyautogui.keyDown(sys.argv[2]);time.sleep(.15);pyautogui.keyUp(sys.argv[2]);time.sleep(.4)
elif action=='click':
    x,y=map(int,sys.argv[2:4]);assert 0<=x<rect[2]-rect[0] and 0<=y<rect[3]-rect[1]
    pyautogui.click(rect[0]+x,rect[1]+y,duration=.15)
elif action=='hold':
    duration=float(sys.argv[3]);assert 0<duration<=3
    pyautogui.keyDown(sys.argv[2]);time.sleep(duration);pyautogui.keyUp(sys.argv[2])
elif action=='mouse':pyautogui.click(button=sys.argv[2])
elif action=='look':
    dx,dy=map(int,sys.argv[2:4]);assert abs(dx)<=2000 and abs(dy)<=600
    ctypes.windll.user32.mouse_event(0x0001,dx,dy,0,0)
elif action=='record':
    profile=sys.argv[2];assert profile in ['idle','attack','run']
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg,'ffmpeg required'
    out=ROOT/'artifacts/runtime_review';out.mkdir(exist_ok=True)
    video=out/(time.strftime('%Y%m%d_%H%M%S')+'_'+profile+'.mp4')
    duration=8 if profile!='run' else 5
    with video.with_suffix('.log').open('wb') as log:
        recorder=subprocess.Popen([ffmpeg,'-hide_banner','-loglevel','warning','-y','-f','gdigrab',
            '-framerate','20','-draw_mouse','0','-offset_x',str(rect[0]),'-offset_y',str(rect[1]),
            '-video_size',str(rect[2]-rect[0])+'x'+str(rect[3]-rect[1]),'-i','desktop','-t',str(duration),'-an','-vf','scale=1280:-2',
            '-c:v','libx264','-preset','veryfast','-crf','18',str(video)],stdout=log,stderr=subprocess.STDOUT)
        try:
            time.sleep(1.)
            assert win32gui.GetForegroundWindow()==hwnd
            if profile=='attack':
                for _ in range(3):
                    pyautogui.mouseDown(button='left');time.sleep(.15);pyautogui.mouseUp(button='left');time.sleep(.65)
            elif profile=='run':
                pyautogui.keyDown('w');time.sleep(1.);pyautogui.keyUp('w')
            recorder.wait(timeout=20)
        finally:
            pyautogui.keyUp('w');pyautogui.mouseUp(button='left')
            if recorder.poll() is None:recorder.terminate();recorder.wait(timeout=5)
    assert recorder.returncode==0 and video.stat().st_size>1000
    print('GAME_REVIEW_VIDEO',str(video))
elif action!='shot':raise SystemExit('Unsupported game review action')
time.sleep(.3)
out=ROOT/'artifacts/runtime_review';out.mkdir(exist_ok=True)
path=out/(time.strftime('%Y%m%d_%H%M%S')+'_'+action+'.png')
ImageGrab.grab(bbox=win32gui.GetWindowRect(hwnd)).save(path)
print(json.dumps({'window':hwnd,'pid':pid,'title':title,'rect':rect,'screenshot':str(path)},ensure_ascii=False))
