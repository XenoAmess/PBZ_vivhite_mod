"""Operate only the visible official Epic launcher during the authorized install.

Coordinates are relative to its current window, and actions are chosen after
inspecting screenshots. Never targets the game or changes launcher auth data.
"""
import json
import sys
import time
from pathlib import Path
import win32gui
import win32con
import pyautogui
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parents[1]
windows=[]
def visit(h,_):
    title=win32gui.GetWindowText(h)
    rect=win32gui.GetWindowRect(h)
    if 'Epic Games' in title and win32gui.IsWindowVisible(h) and rect[2]-rect[0]>800:
        windows.append(h)
win32gui.EnumWindows(visit,None)
assert windows,'No visible Epic launcher window'
h=windows[0]
if win32gui.IsIconic(h):win32gui.ShowWindow(h,win32con.SW_RESTORE)
try:win32gui.SetForegroundWindow(h)
except Exception:pass
rect=win32gui.GetWindowRect(h)
action=sys.argv[1] if len(sys.argv)>1 else 'screenshot'
if action!='screenshot':
    assert win32gui.GetForegroundWindow()==h,'Epic must be the foreground window before interaction'
if action=='click':
    x,y=map(int,sys.argv[2:4]);assert 0<=x<rect[2]-rect[0] and 0<=y<rect[3]-rect[1]
    pyautogui.click(rect[0]+x,rect[1]+y)
elif action=='type':pyautogui.write(sys.argv[2],interval=.015)
elif action=='key':pyautogui.hotkey(*sys.argv[2:])
elif action!='screenshot':raise SystemExit('Unknown action')
time.sleep(1)
path=ROOT/'artifacts/epic_launcher.png'
ImageGrab.grab(bbox=win32gui.GetWindowRect(h)).save(path)
print(json.dumps({'window':h,'rect':rect,'action':action,'screenshot':str(path)}))
