"""
XTB Calibration Tool — interactive screen-coordinate mapper.

Run this script once whenever your screen resolution or browser zoom level
changes.  Hover your mouse over each UI element in xStation 5 when prompted;
the script records the coordinates and writes them to xtb_coordinates.py.

Usage:
    python src/calibrate_xtb.py
"""

import re
import time

import pyautogui
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().with_name('xtb_coordinates.py')

print("="*80)
print("XTB CALIBRATION - Finding UI coordinates")
print("="*80)
print("\nInstructions:")
print("1. Open XTB xStation 5 in your browser")
print("2. Log in to your demo account")
print("3. Search for any stock (e.g. XTB) so all UI elements are visible")
print("4. The script will record the mouse position every 20 seconds")
print("\nWARNING: You have 20 seconds to move the mouse over each element!")
print("To abort: Ctrl+C")
print("="*80)

print("\nStarting in 5 seconds...")
for i in range(5, 0, -1):
    print(f"{i}...")
    time.sleep(1)

print("\nELEMENTS TO CALIBRATE:")
print("-" * 80)
print("1. CONFIRM_TRANSACTION_BUTTON - Confirm transaction button (final step of a trade)")
print("2. MARKET_WATCH_TAB - Market Watch tab (where the search bar is)")
print("3. OPEN_POSITIONS_TAB - Open Positions tab (list of active positions)")
print("-" * 80)

coordinates = {}

elements = [
    ('CONFIRM_TRANSACTION_BUTTON', 'Confirm transaction button (final step)'),
    ('MARKET_WATCH_TAB', 'Market Watch tab (where the search bar is)'),
    ('OPEN_POSITIONS_TAB', 'Open Positions tab'),
]

for element_name, description in elements:
    print(f"\n{'='*80}")
    print(f"CALIBRATING: {description}")
    print("="*80)
    print(f"You have 20 seconds - move the mouse OVER the element!")

    for i in range(20, 0, -1):
        x, y = pyautogui.position()
        print(f"\r{i:2d}s | Mouse position: ({x:4d}, {y:4d})   ", end='', flush=True)
        time.sleep(1)

    x, y = pyautogui.position()
    coordinates[element_name] = (x, y)

    print(f"\nSaved: {element_name} = ({x}, {y})")

    if element_name != elements[-1][0]:
        print("   Next element in 2 seconds...")
        time.sleep(2)

print("\n" + "="*80)
print("ALL COORDINATES")
print("="*80)

print("\nCalibrated coordinates:")
for name, (x, y) in coordinates.items():
    print(f"{name}_X = {x}")
    print(f"{name}_Y = {y}")

print("\n" + "="*80)
print("SAVING COORDINATES")
print("="*80)

existing_coords = {}
try:
    with CONFIG_PATH.open('r', encoding='utf-8') as f:
        content = f.read()
        for line in content.split('\n'):
            if '_X = ' in line and not line.startswith('#'):
                name = line.split('_X = ')[0].strip()
                if name:
                    x_match = re.search(f'{name}_X = (\\d+)', content)
                    y_match = re.search(f'{name}_Y = (\\d+)', content)
                    if x_match and y_match:
                        existing_coords[name] = (int(x_match.group(1)), int(y_match.group(1)))

    print(f"Found {len(existing_coords)} existing coordinates")
except FileNotFoundError:
    print("No existing file - creating new one")

all_coords = {**existing_coords, **coordinates}

with CONFIG_PATH.open('w', encoding='utf-8') as f:
    f.write('"""\n')
    f.write('XTB xStation 5 - UI element coordinates\n')
    f.write('"""\n\n')

    for name, (x, y) in all_coords.items():
        f.write(f"{name}_X = {x}\n")
        f.write(f"{name}_Y = {y}\n")
        f.write(f"{name}_XY = ({x}, {y})\n\n")

print(f"\nSaved to: {CONFIG_PATH}")
print(f"   Updated {len(coordinates)} coordinates")
print(f"   Preserved {len(existing_coords)} existing coordinates")
print("\nYou can now use these coordinates in xtb_trader.py!")
