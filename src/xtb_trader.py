"""
XTB Trader — automates order execution on XTB xStation 5 via PyAutoGUI.

Key responsibilities:
  - buy(ticker, amount)  — searches stock, enters order, clicks confirm
  - sell(ticker)         — finds open position row via OCR, clicks sell
  - get_open_positions() — OCR-reads the positions table and returns live P&L
  - positions_state      — persists peak-profit and open-date for risk management

UI coordinates for all buttons are stored in xtb_coordinates.py.
"""

import pyautogui
import time
from datetime import datetime
import json
import os
import pytesseract
import numpy as np

EASYOCR_AVAILABLE = None
EASYOCR_READER = None


def _get_easyocr_reader():
    global EASYOCR_AVAILABLE, EASYOCR_READER

    if EASYOCR_AVAILABLE is None:
        try:
            import easyocr

            print("[OCR] Initializing EasyOCR for Polish and English...")
            EASYOCR_READER = easyocr.Reader(['pl', 'en'], gpu=False, verbose=False)
            EASYOCR_AVAILABLE = True
        except Exception as error:
            EASYOCR_AVAILABLE = False
            print(f"[WARNING] EasyOCR unavailable; using Tesseract: {error}")

    return EASYOCR_READER

import config
import notifications

TESSERACT_TABLE_CONFIG = r'--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.%+- '
TESSERACT_DEFAULT_CONFIG = r'--psm 6'

try:
    from xtb_coordinates import (
        SEARCH_BOX_X, SEARCH_BOX_Y,
        SEARCH_BUTTON_X, SEARCH_BUTTON_Y,
        STOCK_ICON_X, STOCK_ICON_Y,
        PLACE_ORDER_BUTTON_X, PLACE_ORDER_BUTTON_Y,
        AMOUNT_FIELD_X, AMOUNT_FIELD_Y,
        BUY_BUTTON_X, BUY_BUTTON_Y,
        SELL_BUTTON_X, SELL_BUTTON_Y,
        CONFIRM_TRANSACTION_BUTTON_X, CONFIRM_TRANSACTION_BUTTON_Y,
        MARKET_WATCH_TAB_X, MARKET_WATCH_TAB_Y,
        OPEN_POSITIONS_TAB_X, OPEN_POSITIONS_TAB_Y
    )
    COORDS_LOADED = True
except ImportError:
    print("[WARNING] xtb_coordinates.py not found - run: python src/calibrate_xtb.py")
    COORDS_LOADED = False


class XTBTrader:
    """Automates trading on XTB xStation 5."""

    def __init__(self):
        pyautogui.PAUSE = config.PYAUTOGUI_PAUSE
        pyautogui.FAILSAFE = config.PYAUTOGUI_FAILSAFE

        self.trade_log = []
        self.positions_state = self.load_positions_state()

        print("[OCR] Using Tesseract OCR")

    def load_positions_state(self):
        """Load position state from JSON file."""
        try:
            if os.path.exists(config.XTB_POSITIONS_STATE_FILE):
                with open(config.XTB_POSITIONS_STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"[WARNING] Failed to load position state: {e}")
            return {}

    def save_positions_state(self):
        """Save position state to JSON file."""
        try:
            with open(config.XTB_POSITIONS_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.positions_state, f, ensure_ascii=False, indent=2)
            if config.VERBOSE_LOGGING:
                print(f"[SAVE] Position state saved: {config.XTB_POSITIONS_STATE_FILE}")
        except Exception as e:
            print(f"[ERROR] Failed to save position state: {e}")

    def update_position_state(self, ticker, current_profit_pct):
        """
        Update peak profit and reading history for a position.
        Does NOT create new positions — only buy() does that.
        Legacy positions (not in state) are silently skipped.
        """
        if ticker not in self.positions_state:
            if config.VERBOSE_LOGGING:
                print(f"[STATE] {ticker}: Legacy position - skipping state update")
            return

        old_peak = self.positions_state[ticker]['peak_profit_pct']

        if current_profit_pct > old_peak:
            self.positions_state[ticker]['peak_profit_pct'] = current_profit_pct
            if config.VERBOSE_LOGGING:
                print(f"[STATE] {ticker}: New peak profit {old_peak:+.2f}% -> {current_profit_pct:+.2f}%")

        if 'profit_history' not in self.positions_state[ticker]:
            self.positions_state[ticker]['profit_history'] = []

        self.positions_state[ticker]['profit_history'].append(current_profit_pct)

        if len(self.positions_state[ticker]['profit_history']) > 3:
            self.positions_state[ticker]['profit_history'] = self.positions_state[ticker]['profit_history'][-3:]

        self.save_positions_state()

    def get_validated_profit(self, ticker):
        """
        Return the average profit only if the last 3 readings are consistent (within 5%).
        Prevents erroneous sells caused by a single bad OCR read.
        Returns None if fewer than 3 readings or readings are inconsistent.
        """
        if ticker not in self.positions_state:
            return None

        history = self.positions_state[ticker].get('profit_history', [])

        if len(history) < 3:
            print(f"[VALIDATION] {ticker}: Only {len(history)}/3 readings - waiting for more")
            return None

        last_3 = history[-3:]

        min_profit = min(last_3)
        max_profit = max(last_3)
        diff = max_profit - min_profit

        VALIDATION_THRESHOLD = 5.0

        if diff <= VALIDATION_THRESHOLD:
            avg_profit = sum(last_3) / 3
            print(f"[VALIDATION] {ticker}: 3 consistent readings [{last_3[0]:.2f}%, {last_3[1]:.2f}%, {last_3[2]:.2f}%] -> avg: {avg_profit:.2f}%")
            return avg_profit
        else:
            print(f"[VALIDATION] {ticker}: Readings not consistent [{last_3[0]:.2f}%, {last_3[1]:.2f}%, {last_3[2]:.2f}%] (diff: {diff:.2f}%, threshold: {VALIDATION_THRESHOLD}%) - waiting")
            return None

    def remove_position_state(self, ticker):
        """Remove a position from state (after sell)."""
        if ticker in self.positions_state:
            del self.positions_state[ticker]
            self.save_positions_state()
            print(f"[STATE] Removed position from state: {ticker}")

    def find_button_with_easyocr(self, text_to_find, region=None, confidence=0.3):
        """
        Find a button on screen using EasyOCR.
        Returns (x, y) of the text centre, or None if not found.
        """
        reader = _get_easyocr_reader()
        if reader is None:
            print("[OCR] EasyOCR not available - falling back to Tesseract")
            return self.find_button_by_text(text_to_find, region, confidence)

        try:
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            img_np = np.array(screenshot)
            results = reader.readtext(img_np)

            found_texts = []

            for (bbox, text, conf) in results:
                found_texts.append(f"{text}({conf*100:.0f}%)")

                if text and text_to_find.lower() in text.lower() and conf >= confidence:
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]

                    center_x = int(sum(x_coords) / len(x_coords))
                    center_y = int(sum(y_coords) / len(y_coords))

                    if region:
                        center_x += region[0]
                        center_y += region[1]

                    print(f"[EasyOCR] Found '{text}' at ({center_x}, {center_y}), confidence: {conf*100:.0f}%")
                    return (center_x, center_y)

            print(f"[EasyOCR] Text '{text_to_find}' not found (threshold: {confidence*100:.0f}%)")

            if config.VERBOSE_LOGGING and found_texts:
                print(f"[EasyOCR] Found {len(found_texts)} texts: {', '.join(found_texts[:10])}")

            return None

        except Exception as e:
            print(f"[EasyOCR ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None

    def find_button_by_text(self, text_to_find, region=None, confidence=0.2):
        """
        Find a button on screen using Tesseract OCR.
        Returns (x, y) of the text centre, or None if not found.
        """
        try:
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            screenshot_gray = screenshot.convert('L')

            ocr_data = pytesseract.image_to_data(
                screenshot_gray,
                lang='pol+eng',
                config=TESSERACT_DEFAULT_CONFIG,
                output_type=pytesseract.Output.DICT
            )

            found_texts = []

            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != '-1' else 0

                if text and conf > 10:
                    found_texts.append(f"{text}({conf}%)")

                if text and text_to_find.lower() in text.lower() and conf >= (confidence * 100):
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]

                    center_x = x + w // 2
                    center_y = y + h // 2

                    if region:
                        center_x += region[0]
                        center_y += region[1]

                    print(f"[OCR] Found '{text}' at ({center_x}, {center_y}), confidence: {conf}%")
                    return (center_x, center_y)

            print(f"[OCR] Text '{text_to_find}' not found (threshold: {confidence*100}%)")

            if config.VERBOSE_LOGGING and found_texts:
                print(f"[OCR] Found {len(found_texts)} texts: {', '.join(found_texts[:10])}")

            return None

        except Exception as e:
            print(f"[OCR ERROR] {e}")
            import traceback
            traceback.print_exc()
            return None

    def click_confirm_button(self, screenshot_name=None):
        """
        Find and click the confirm button via OCR.
        Returns True if clicked, False if not found.
        """
        print(f"[XTB] Searching for confirm button via OCR...")

        button_pos = None
        text_variants = [
            'Potwierdź',
            'Potwierdz',
            'POTWIERDŹ',
            'POTWIERDZ',
            'Potwierdzam',
            'Confirm',
            'CONFIRM',
            'OK',
            'Zatwierdź',
            'Zatwierdzam'
        ]

        if _get_easyocr_reader() is not None:
            print(f"[OCR] Using EasyOCR (better for Polish characters)...")

            for text_variant in text_variants:
                button_pos = self.find_button_with_easyocr(text_variant, region=None, confidence=0.3)
                if button_pos:
                    print(f"[EasyOCR] Found variant: '{text_variant}'")
                    break

        if not button_pos:
            print(f"[OCR] EasyOCR failed - trying Tesseract...")

            for text_variant in text_variants:
                button_pos = self.find_button_by_text(text_variant, region=None, confidence=0.2)
                if button_pos:
                    print(f"[Tesseract] Found variant: '{text_variant}'")
                    break

        if button_pos:
            print(f"[XTB] Clicking confirm button at: {button_pos}")
            pyautogui.click(x=button_pos[0], y=button_pos[1])
            time.sleep(1)

            if screenshot_name:
                self.take_screenshot(screenshot_name)

            return True
        else:
            print(f"[XTB] WARNING: Confirm button not found via OCR!")
            print(f"[XTB] Tried variants: {text_variants}")

            if config.VERBOSE_LOGGING:
                print(f"[DEBUG] Taking debug screenshot...")
                debug_screenshot = pyautogui.screenshot()
                debug_path = os.path.join(config.SCREENSHOT_DIR, "debug_confirm_button_search.png")
                debug_screenshot.save(debug_path)
                print(f"[DEBUG] Screenshot saved: {debug_path}")

            if COORDS_LOADED:
                print(f"[XTB] Falling back to saved coordinates from xtb_coordinates.py...")
                pyautogui.click(x=CONFIRM_TRANSACTION_BUTTON_X, y=CONFIRM_TRANSACTION_BUTTON_Y)
                time.sleep(1)

                if screenshot_name:
                    self.take_screenshot(screenshot_name + "_fallback")

                return True

            return False

    def take_screenshot(self, name):
        """Take a screenshot as trade evidence."""
        if not config.XTB_SCREENSHOT_ON_TRADE:
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name}_{timestamp}.png"
        filepath = os.path.join(config.SCREENSHOT_DIR, filename)

        try:
            pyautogui.screenshot(filepath)
            print(f"[SCREENSHOT] Saved: {filepath}")
            return filepath
        except Exception as e:
            if config.VERBOSE_LOGGING:
                print(f"[WARNING] Screenshot failed (missing Screen Recording permission): {e}")
            return None

    def place_market_order(self, action, ticker, amount=None):
        """
        Place a market order on XTB xStation 5.

        Workflow (11 steps):
        1. Click Market Watch tab
        2. Click search box
        3. Type ticker
        4. Click search button
        5. Click stock icon in results
        6. Click Place Order button
        7. Click amount field
        8. Select all (Cmd+A) to clear default amount
        9. Type desired amount
        10. Click Buy / Sell button
        11. Click confirm button (located via OCR)
        """
        if amount is None:
            amount = config.XTB_DEFAULT_AMOUNT

        print(f"\n{'='*80}")
        print(f"[XTB] >>> PLACING {action} ORDER <<<")
        print(f"      Ticker: {ticker}")
        print(f"      Amount: {amount} PLN")
        print(f"      Type: MARKET ORDER")
        print("="*80)

        try:
            if not COORDS_LOADED:
                print("[ERROR] No coordinates! Run: python src/calibrate_xtb.py")
                return None

            print(f"[XTB] Step 1/11: Clicking Market Watch tab...")
            pyautogui.click(x=MARKET_WATCH_TAB_X, y=MARKET_WATCH_TAB_Y)
            time.sleep(0.5)
            self.take_screenshot(f"step1_market_watch_{ticker}")

            print(f"[XTB] Step 2/11: Clicking search box...")
            pyautogui.click(x=SEARCH_BOX_X, y=SEARCH_BOX_Y)
            time.sleep(0.5)
            self.take_screenshot(f"step2_search_box_{ticker}")

            print(f"[XTB] Step 3/11: Typing ticker '{ticker}'...")
            pyautogui.write(ticker, interval=0.1)
            time.sleep(0.5)
            self.take_screenshot(f"step3_typed_{ticker}")

            print(f"[XTB] Step 4/11: Clicking search button...")
            pyautogui.click(x=SEARCH_BUTTON_X, y=SEARCH_BUTTON_Y)
            time.sleep(1)
            self.take_screenshot(f"step4_search_results_{ticker}")

            print(f"[XTB] Step 5/11: Clicking stock icon '{ticker}' in results...")
            pyautogui.click(x=STOCK_ICON_X, y=STOCK_ICON_Y)
            time.sleep(1)
            self.take_screenshot(f"step5_stock_selected_{ticker}")

            print(f"[XTB] Step 6/11: Clicking Place Order button...")
            pyautogui.click(x=PLACE_ORDER_BUTTON_X, y=PLACE_ORDER_BUTTON_Y)
            time.sleep(1)
            self.take_screenshot(f"step6_order_window_{ticker}")

            print(f"[XTB] Step 7/11: Clicking amount field...")
            pyautogui.click(x=AMOUNT_FIELD_X, y=AMOUNT_FIELD_Y)
            time.sleep(0.3)

            print(f"[XTB] Step 8/11: Clearing default amount...")
            pyautogui.hotkey('command', 'a')
            time.sleep(0.2)

            print(f"[XTB] Step 9/11: Typing amount: {amount} PLN...")
            pyautogui.write(str(amount), interval=0.1)
            time.sleep(0.5)
            self.take_screenshot(f"step9_amount_entered_{ticker}")

            print(f"[XTB] Step 10/11: Clicking '{action}' button...")
            if action == 'BUY':
                pyautogui.click(x=BUY_BUTTON_X, y=BUY_BUTTON_Y)
            else:
                pyautogui.click(x=SELL_BUTTON_X, y=SELL_BUTTON_Y)

            time.sleep(1)
            self.take_screenshot(f"step10_confirm_dialog_{ticker}")

            print(f"[XTB] Step 11/11: Clicking confirm button...")
            self.click_confirm_button(f"step11_order_executed_{ticker}")
            time.sleep(1)

            trade = {
                'timestamp': datetime.now().isoformat(),
                'action': action,
                'ticker': ticker,
                'amount': amount,
                'status': 'EXECUTED',
                'order_type': 'MARKET'
            }

            self.trade_log.append(trade)
            self.save_trade_log()

            self.positions_state[ticker] = {
                'peak_profit_pct': 0.0,
                'opened_at': datetime.now().isoformat()
            }
            self.save_positions_state()

            print(f"\n[SUCCESS] {action} order for {ticker} placed successfully!")
            print(f"          Amount: {amount} PLN")
            print(f"[INFO] Verify execution in XTB")

            return trade

        except Exception as e:
            print(f"[ERROR] Failed to place order: {e}")
            self.take_screenshot(f"error_{action}_{ticker}")
            return None

    def buy(self, ticker, amount=None):
        """Buy shares for the given PLN amount."""
        return self.place_market_order('BUY', ticker, amount)

    def get_open_positions(self):
        """
        Read all open positions from the XTB positions table via OCR.

        Workflow:
        1. Click Open Positions tab
        2. Scan screen with OCR
        3. Parse position data

        Returns a list of dicts with ticker, profit_pct, and raw row data.
        """
        print(f"\n{'='*80}")
        print(f"[XTB] >>> FETCHING OPEN POSITIONS <<<")
        print("="*80)

        try:
            if not COORDS_LOADED:
                print("[ERROR] No coordinates! Run: python src/calibrate_xtb.py")
                return []

            print(f"[XTB] Step 1/3: Clicking Open Positions tab...")
            pyautogui.click(x=OPEN_POSITIONS_TAB_X, y=OPEN_POSITIONS_TAB_Y)
            time.sleep(1)
            self.take_screenshot("get_positions_step1_tab")

            print(f"[XTB] Step 2/3: Scanning screen for tickers...")

            screen_width, screen_height = pyautogui.size()
            print(f"[OCR] Scanning full screen: {screen_width}x{screen_height} px")

            screenshot = pyautogui.screenshot()

            if config.VERBOSE_LOGGING:
                debug_path = os.path.join(config.SCREENSHOT_DIR, "debug_open_positions_table.png")
                screenshot.save(debug_path)
                print(f"[OCR] Debug screenshot: {debug_path}")

            screenshot_gray = screenshot.convert('L')

            tickers_to_find = list(self.positions_state.keys())

            if not tickers_to_find:
                print("[INFO] No tickers in positions_state - nothing to check")
                return []

            print(f"[INFO] Looking for {len(tickers_to_find)} tickers: {tickers_to_find}")

            print("[OCR] Scanning table...")
            ocr_data = pytesseract.image_to_data(
                screenshot_gray,
                lang='pol+eng',
                config=TESSERACT_DEFAULT_CONFIG,
                output_type=pytesseract.Output.DICT
            )

            all_texts = []
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != '-1' else 0

                if text and conf > 30:
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    all_texts.append({'text': text, 'x': x, 'y': y, 'conf': conf})

            print(f"[OCR] Found {len(all_texts)} text elements in table")

            print(f"[XTB] Step 3/3: Matching tickers to table rows...")
            positions = []

            for ticker in tickers_to_find:
                print(f"\n[SEARCH] Looking for ticker: {ticker}")

                ticker_pl_format = f"{ticker.upper()}.PL"

                ticker_variants = [
                    ticker_pl_format,
                    f"{ticker.upper()}.WA",
                    ticker.upper()
                ]

                print(f"[INFO] Possible ticker formats: {ticker_variants}")

                ticker_found = None
                ticker_y = None
                ticker_x = None

                for variant in ticker_variants:
                    for item in all_texts:
                        clean_text = item['text'].replace('©', '').strip().upper()

                        if clean_text == variant:
                            ticker_found = item['text']
                            ticker_y = item['y']
                            ticker_x = item['x']
                            print(f"[FOUND] Found '{ticker}' as '{ticker_found}' at (x={ticker_x}, y={ticker_y})")
                            break

                    if ticker_found:
                        break

                if not ticker_found:
                    print(f"[WARNING] Ticker '{ticker}' (formats: {ticker_variants}) not found on screen - position may be closed")
                    continue

                Y_THRESHOLD = 20
                row_texts = []

                for item in all_texts:
                    if abs(item['y'] - ticker_y) < Y_THRESHOLD:
                        row_texts.append(item)

                row_texts_sorted = sorted(row_texts, key=lambda t: t['x'])
                row_texts_values = [t['text'] for t in row_texts_sorted]

                print(f"[ROW] Row for {ticker}: {row_texts_values}")

                profit_text = None
                profit_value = None

                for text in row_texts_values:
                    if '%' in text:
                        try:
                            profit_clean = text.replace('%', '').replace(',', '.').strip()

                            if profit_clean.startswith('+'):
                                profit_clean = profit_clean[1:]

                            cleaned_chars = []
                            for i, c in enumerate(profit_clean):
                                if c.isdigit() or c in ['.', '-']:
                                    cleaned_chars.append(c)
                                elif c == '-' and i == 0:
                                    cleaned_chars.append(c)
                                elif len(cleaned_chars) > 0 and not c.isdigit():
                                    break

                            profit_clean = ''.join(cleaned_chars)

                            if profit_clean and profit_clean not in ['-', '+', '.']:
                                profit_value = float(profit_clean)
                                profit_text = text
                                print(f"[PROFIT] Found profit: {profit_value}% (raw: '{profit_text}')")
                                break
                        except Exception as e:
                            print(f"[ERROR] Failed to parse profit '{text}': {e}")
                            continue

                if profit_value is None:
                    print(f"[WARNING] Profit not found for {ticker} in row: {row_texts_values}")
                    continue

                position = {
                    'ticker': ticker,
                    'ticker_ocr': ticker_found,
                    'profit_pct': profit_value,
                    'profit_text': profit_text,
                    'row_texts': row_texts_values,
                    'profit_pct_source': 'OCR_SCREEN'
                }

                positions.append(position)
                print(f"[SUCCESS] Position added: {ticker} ({profit_value:+.2f}%)")

            print(f"\n[SUCCESS] Found {len(positions)} open positions")
            return positions

        except Exception as e:
            print(f"[ERROR] Error scanning positions: {e}")
            import traceback
            traceback.print_exc()
            return []

    def sell(self, ticker):
        """
        Close an open position by selling via the Open Positions tab.

        Workflow:
        1. Click Open Positions tab
        2. Find ticker via OCR
        3. Click sell button (fixed X column, Y from OCR)
        4. Click confirm button
        """
        print(f"\n{'='*80}")
        print(f"[XTB] >>> SELLING POSITION <<<")
        print(f"      Ticker: {ticker}")
        print(f"      Type: Close position")
        print("="*80)

        try:
            if not COORDS_LOADED:
                print("[ERROR] No coordinates! Run: python src/calibrate_xtb.py")
                return None

            print(f"[XTB] Step 1/4: Clicking Open Positions tab...")
            pyautogui.click(x=OPEN_POSITIONS_TAB_X, y=OPEN_POSITIONS_TAB_Y)
            time.sleep(1)
            self.take_screenshot(f"sell_step1_open_positions_{ticker}")

            print(f"[XTB] Step 2/4: Searching for '{ticker}' in .PL format...")

            screen_width, screen_height = pyautogui.size()
            print(f"[OCR] Scanning full screen for {ticker}.PL...")

            screenshot = pyautogui.screenshot()

            if config.VERBOSE_LOGGING:
                debug_screenshot_path = os.path.join(config.SCREENSHOT_DIR, f"debug_sell_fullscreen_{ticker}.png")
                screenshot.save(debug_screenshot_path)
                print(f"[OCR] Debug screenshot: {debug_screenshot_path}")

            screenshot_gray = screenshot.convert('L')
            ocr_data = pytesseract.image_to_data(
                screenshot_gray,
                lang='pol+eng',
                config=TESSERACT_DEFAULT_CONFIG,
                output_type=pytesseract.Output.DICT
            )

            all_texts = []
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != '-1' else 0

                if text and conf > 30:
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    all_texts.append({'text': text, 'x': x, 'y': y, 'conf': conf})

            print(f"[OCR] Found {len(all_texts)} text elements on screen")

            ticker_pl_format = f"{ticker.upper()}.PL"
            ticker_variants = [
                ticker_pl_format,
                f"{ticker.upper()}.WA",
                ticker.upper()
            ]

            print(f"[INFO] Searching for variants: {ticker_variants}")

            ticker_position = None
            ticker_found = None

            for variant in ticker_variants:
                for item in all_texts:
                    if item['text'].upper() == variant:
                        ticker_position = (item['x'], item['y'])
                        ticker_found = item['text']
                        print(f"[OCR] Found '{ticker_found}' at {ticker_position}, confidence: {item['conf']}%")
                        break

                if ticker_position:
                    break

            if not ticker_position:
                print(f"[ERROR] Ticker '{ticker}' (formats: {ticker_variants}) not found on screen!")
                print(f"[ERROR] Make sure:")
                print(f"        1. You have an open position for '{ticker}'")
                print(f"        2. {ticker_pl_format} is visible on screen")
                print(f"        3. You are on the Open Positions tab")

                print(f"[DEBUG] First 20 found texts:")
                for i, item in enumerate(all_texts[:20], 1):
                    print(f"        {i}. '{item['text']}' (confidence: {item['conf']}%)")

                self.take_screenshot(f"sell_error_ticker_not_found_{ticker}")
                return None

            sell_button_x = config.XTB_SELL_X_OFFSET
            sell_button_y = ticker_position[1]

            print(f"[XTB] Step 3/4: Clicking sell button at ({sell_button_x}, {sell_button_y})...")
            print(f"[XTB] (X={config.XTB_SELL_X_OFFSET} is fixed for all stocks, Y={sell_button_y} from OCR)")
            pyautogui.click(x=sell_button_x, y=sell_button_y)
            time.sleep(1)
            self.take_screenshot(f"sell_step3_sell_button_{ticker}")

            print(f"[XTB] Step 4/4: Clicking confirm button...")
            self.click_confirm_button(f"sell_step4_confirmed_{ticker}")
            time.sleep(1)

            trade = {
                'timestamp': datetime.now().isoformat(),
                'action': 'SELL',
                'ticker': ticker,
                'amount': None,
                'status': 'EXECUTED',
                'order_type': 'CLOSE_POSITION'
            }

            self.trade_log.append(trade)
            self.save_trade_log()

            if ticker in self.positions_state:
                del self.positions_state[ticker]
                self.save_positions_state()
                print(f"[INFO] {ticker} removed from position state")

            print(f"\n[SUCCESS] Position for {ticker} closed (sold)!")
            print(f"[INFO] Verify execution in XTB")

            return trade

        except Exception as e:
            print(f"[ERROR] Sell failed: {e}")
            import traceback
            traceback.print_exc()
            self.take_screenshot(f"sell_error_{ticker}")
            return None

    def check_positions_and_sell(self):
        """
        Check all open positions and auto-sell if any exit condition is met:
        - TRAILING STOP LOSS: profit dropped X% from peak
        - TAKE PROFIT: profit >= configured threshold
        - MAX HOLDING DAYS: position held longer than allowed

        Returns a list of executed sell trades.
        """
        print(f"\n{'='*80}")
        print(f"[XTB] >>> CHECKING POSITIONS (TRAILING STOP / TAKE PROFIT / HOLDING DAYS) <<<")
        print("="*80)

        positions = self.get_open_positions()

        if not positions:
            print("[INFO] No open positions")
            return []

        print(f"\n[INFO] Found {len(positions)} open positions")

        sells = []
        now = datetime.now()

        for pos in positions:
            ticker = pos['ticker']
            current_profit_pct_raw = pos['profit_pct']

            self.update_position_state(ticker, current_profit_pct_raw)

            validated_profit = self.get_validated_profit(ticker)

            if validated_profit is None:
                print(f"\n--- SKIPPING: {ticker} ---")
                print(f"    Waiting for more consistent readings ({len(self.positions_state[ticker].get('profit_history', []))} so far)")
                continue

            current_profit_pct = validated_profit

            state = self.positions_state.get(ticker, {})
            peak_profit_pct = state.get('peak_profit_pct', current_profit_pct)
            opened_at_str = state.get('opened_at', now.isoformat())
            opened_at = datetime.fromisoformat(opened_at_str)
            holding_days = (now - opened_at).days

            print(f"\n--- CHECKING: {ticker} ---")
            print(f"    Current profit (validated): {current_profit_pct:+.2f}%")
            print(f"    Peak profit: {peak_profit_pct:+.2f}%")
            print(f"    Opened at: {opened_at.strftime('%Y-%m-%d %H:%M')}")
            print(f"    Days held: {holding_days}")

            should_sell = False
            reason = ""

            if current_profit_pct >= config.XTB_TAKE_PROFIT_PCT:
                should_sell = True
                reason = f"TAKE PROFIT (profit {current_profit_pct:+.2f}% >= {config.XTB_TAKE_PROFIT_PCT}%)"

            elif peak_profit_pct - current_profit_pct >= config.XTB_TRAILING_STOP_LOSS_PCT:
                should_sell = True
                drop = peak_profit_pct - current_profit_pct
                reason = f"TRAILING STOP LOSS (drop {drop:.2f}% from peak {peak_profit_pct:+.2f}%)"

            elif holding_days >= config.XTB_MAX_HOLDING_DAYS:
                should_sell = True
                reason = f"MAX HOLDING DAYS (held {holding_days} days >= {config.XTB_MAX_HOLDING_DAYS} days)"

            if should_sell:
                print(f"    [SELL] {reason}")

                result = self.sell(ticker)

                if result:
                    result['reason'] = reason
                    result['profit_pct'] = current_profit_pct
                    result['peak_profit_pct'] = peak_profit_pct
                    result['holding_days'] = holding_days
                    sells.append(result)

                    notifications.notify_sell(ticker, reason, current_profit_pct)
                    self.remove_position_state(ticker)

                    print(f"    Sold {ticker}")
                else:
                    print(f"    [ERROR] Failed to sell {ticker}")
                    notifications.notify_error(f"Failed to sell {ticker}")
            else:
                print(f"    [HOLD] Keeping position:")
                print(f"       - Profit < {config.XTB_TAKE_PROFIT_PCT}% (take profit)")
                print(f"       - Drop < {config.XTB_TRAILING_STOP_LOSS_PCT}% from peak (trailing stop)")
                print(f"       - Days < {config.XTB_MAX_HOLDING_DAYS} (max holding time)")

        if sells:
            print(f"\n[SUCCESS] Sold {len(sells)} positions")
        else:
            print(f"\n[INFO] No positions to sell")

        return sells

    def save_trade_log(self):
        """Save the trade log to file."""
        log_file = 'xtb_trade_log.json'

        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.trade_log, f, ensure_ascii=False, indent=2)

            print(f"[SAVE] Trade log saved: {log_file}")

        except Exception as e:
            print(f"[ERROR] Failed to save trade log: {e}")

    def process_signal(self, signal):
        """Process a trading signal and execute the order on XTB."""
        if signal['status'] != 'PENDING':
            print(f"[INFO] Signal already processed: {signal['status']}")
            return

        action = signal['action']
        ticker = signal['ticker']

        print(f"\n{'='*80}")
        print(f"[SIGNAL] Processing signal:")
        print(f"         Action: {action}")
        print(f"         Ticker: {ticker}")
        print(f"         Score: {signal['score']:.2f}")
        print(f"         Article: {signal['news_title'][:60]}...")
        print("="*80)

        if action == 'BUY':
            positions = self.get_open_positions()
            if len(positions) >= config.XTB_MAX_POSITIONS:
                print(f"[REJECT] Already have {len(positions)} positions (max: {config.XTB_MAX_POSITIONS})")
                signal['status'] = 'REJECTED'
                signal['rejected_reason'] = 'MAX_POSITIONS_REACHED'
                return

            from gpw_companies import tickers_match

            buys = [t for t in self.trade_log if t['action'] == 'BUY' and tickers_match(t['ticker'], ticker) and t['status'] == 'EXECUTED']
            sells = [t for t in self.trade_log if t['action'] == 'SELL' and tickers_match(t['ticker'], ticker) and t['status'] == 'EXECUTED']

            if len(buys) > len(sells):
                print(f"[REJECT] Already own {ticker} (trade_log: {len(buys)} BUY, {len(sells)} SELL)")
                signal['status'] = 'REJECTED'
                signal['rejected_reason'] = 'ALREADY_OWNED'
                return

            if any(tickers_match(pos['ticker'], ticker) for pos in positions):
                print(f"[REJECT] Already own {ticker} (detected via OCR)")
                signal['status'] = 'REJECTED'
                signal['rejected_reason'] = 'ALREADY_OWNED'
                return

            print(f"[OK] {ticker} not in portfolio - proceeding to buy")
            result = self.buy(ticker)

        elif action == 'SELL':
            positions = self.get_open_positions()

            from gpw_companies import tickers_match
            has_position = any(tickers_match(pos['ticker'], ticker) for pos in positions)

            if not has_position:
                print(f"[REJECT] No position for {ticker} - skipping sell signal")
                signal['status'] = 'REJECTED'
                signal['rejected_reason'] = 'POSITION_NOT_FOUND'
                return

            print(f"[OK] Position for {ticker} found - selling")
            result = self.sell(ticker)
        else:
            print(f"[ERROR] Unknown action: {action}")
            return

        if result:
            signal['status'] = 'EXECUTED'
            signal['executed_at'] = datetime.now().isoformat()
        else:
            signal['status'] = 'FAILED'


def main():
    """Manual test — buy shares for a given amount."""
    print("="*80)
    print("XTB TRADER - Manual Test")
    print("="*80)

    trader = XTBTrader()

    ticker = input("Enter ticker (e.g. XTB): ").upper()
    amount = input("Enter amount in PLN (Enter = 100): ") or "100"

    print(f"\n[INFO] Starting buy of {ticker} for {amount} PLN in 5 seconds...")
    print("[INFO] Make sure XTB is open and visible on screen!")

    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    print("\n[START] Starting...")
    trader.buy(ticker, int(amount))


if __name__ == "__main__":
    main()

