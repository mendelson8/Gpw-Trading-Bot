"""
GPW News Trading Bot — Entry Point

Starts two concurrent threads:
  1. News monitor — polls PAP RSS / BiznesRadar and emits BUY / SELL signals.
  2. Trading loop — processes pending signals and monitors open positions.

Usage:
    python src/main.py
"""

import threading
import json
import time

import config
from news_monitor import NewsMonitor
from xtb_trader import XTBTrader


class TradingBot:
    """Trading bot combining news analysis with automated order execution."""

    def __init__(self):
        self.news_monitor = NewsMonitor(config.RSS_URL, config.CHECK_INTERVAL)
        self.xtb_trader = XTBTrader() if config.XTB_ENABLED else None
        self.running = True

        if self.xtb_trader:
            self.news_monitor.set_signal_callback(self.on_new_signal)

        print("="*80)
        print("TRADING BOT - News + XTB Automation")
        print("="*80)
        print(f"XTB Enabled: {config.XTB_ENABLED}")
        print(f"Min Buy Score: {config.MIN_BUY_SENTIMENT_SCORE}")
        print(f"Check Interval: {config.CHECK_INTERVAL}s")
        print(f"Immediate buy execution: {bool(self.xtb_trader)}")
        print("="*80)

    def on_new_signal(self, signal):
        """Callback invoked immediately when a new BUY signal is generated."""
        if not self.xtb_trader or signal['status'] != 'PENDING':
            return

        if signal['action'] == 'BUY':
            print(f"\n{'='*80}")
            print(f"[INSTANT] INSTANT BUY SIGNAL EXECUTION")
            print(f"{'='*80}")

            try:
                self.xtb_trader.process_signal(signal)
                self._save_signal_status(signal)
            except Exception as e:
                print(f"[ERROR] Instant execution failed: {e}")
                import traceback
                traceback.print_exc()

    def _save_signal_status(self, updated_signal):
        """Save the updated signal status to file."""
        signals_file = 'trading_signals.json'
        signals = []

        try:
            try:
                with open(signals_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        signals = json.loads(content)
                    else:
                        signals = []
            except FileNotFoundError:
                signals = []
            except json.JSONDecodeError:
                print(f"[WARNING] Failed to parse {signals_file} - resetting to []")
                signals = []

            for i, sig in enumerate(signals):
                if sig.get('timestamp') == updated_signal.get('timestamp') and sig.get('ticker') == updated_signal.get('ticker'):
                    signals[i] = updated_signal
                    break

            with open(signals_file, 'w', encoding='utf-8') as f:
                json.dump(signals, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"[WARNING] Failed to save signal status: {e}")

    def news_monitoring_loop(self):
        """News monitoring thread."""
        iteration = 0
        while self.running:
            iteration += 1
            try:
                print(f"\n[NEWS] Checking feed... (iteration #{iteration})")
                self.news_monitor.check_feed()
            except Exception as e:
                print(f"[ERROR] Error while checking news: {e}")

            time.sleep(config.CHECK_INTERVAL)

    def run(self):
        """Run the bot with parallel news monitoring."""
        try:
            news_thread = threading.Thread(target=self.news_monitoring_loop, daemon=True)
            news_thread.start()
            print("[INFO] News monitoring started in a separate thread")

            iteration = 0
            while self.running:
                iteration += 1

                if config.XTB_ENABLED:
                    print(f"\n[TRADING] Iteration #{iteration}")

                    try:
                        self.process_pending_signals()
                    except Exception as e:
                        print(f"[ERROR] Error processing signals: {e}")

                    try:
                        self.check_open_positions()
                    except Exception as e:
                        print(f"[ERROR] Error checking positions: {e}")

                time.sleep(config.CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n[INFO] Stopped by user")
            self.running = False
            self.show_stats()

    def check_open_positions(self):
        """Check open positions and decide to sell based on stop loss, take profit, or max holding days."""
        from datetime import datetime

        positions = self.xtb_trader.get_open_positions()

        if not positions:
            return

        print(f"\n[INFO] Checking {len(positions)} open positions...")

        for pos in positions:
            ticker = pos['ticker']

            profit_pct_raw = pos['profit_pct']
            if isinstance(profit_pct_raw, str):
                profit_pct_raw = float(profit_pct_raw.replace('%', '').replace('+', ''))
            else:
                profit_pct_raw = float(profit_pct_raw)

            state = self.xtb_trader.positions_state.get(ticker, {})
            peak_profit = state.get('peak_profit_pct', 0.0)
            opened_at_str = state.get('opened_at')

            if not opened_at_str:
                print(f"[WARNING] {ticker}: Legacy position (not in state), using current values")
                print(f"[WARNING] {ticker}: Position will be added to state on next bot action")

                peak_profit = profit_pct_raw
                opened_at = datetime.now()
                days_held = 0
                profit_pct = profit_pct_raw
            else:
                opened_at = datetime.fromisoformat(opened_at_str)
                days_held = (datetime.now() - opened_at).days

                self.xtb_trader.update_position_state(ticker, profit_pct_raw)
                validated_profit = self.xtb_trader.get_validated_profit(ticker)

                if validated_profit is None:
                    print(f"\n[INFO] {ticker}: Waiting for more consistent readings ({len(state.get('profit_history', []))} so far)")
                    print(f"       Raw profit: {profit_pct_raw:.2f}% (unconfirmed)")
                    continue

                profit_pct = validated_profit
                print(f"[VALIDATION] {ticker}: Using validated profit: {profit_pct:.2f}%")

            if opened_at_str and profit_pct > peak_profit:
                peak_profit = profit_pct
                state['peak_profit_pct'] = peak_profit
                self.xtb_trader.positions_state[ticker] = state
                self.xtb_trader.save_positions_state()
                print(f"[INFO] {ticker}: New peak profit: {peak_profit:.2f}%")

            if profit_pct <= config.XTB_STOP_LOSS_PCT:
                print(f"\n[SELL] >>> STOP LOSS for {ticker} <<<")
                print(f"       Loss: {profit_pct:.2f}% (limit: {config.XTB_STOP_LOSS_PCT}%)")
                print(f"       Selling to limit losses.")
                self.xtb_trader.sell(ticker)
                time.sleep(2)
                continue

            drop_from_peak = peak_profit - profit_pct
            if drop_from_peak >= config.XTB_TRAILING_STOP_LOSS_PCT:
                print(f"\n[SELL] >>> TRAILING STOP LOSS for {ticker} <<<")
                print(f"       Peak: {peak_profit:.2f}% | Current: {profit_pct:.2f}% | Drop: {drop_from_peak:.2f}%")
                self.xtb_trader.sell(ticker)
                time.sleep(2)
                continue

            if profit_pct >= config.XTB_TAKE_PROFIT_PCT:
                print(f"\n[SELL] >>> TAKE PROFIT for {ticker} <<<")
                print(f"       Profit: {profit_pct:.2f}% (target: {config.XTB_TAKE_PROFIT_PCT}%)")
                self.xtb_trader.sell(ticker)
                time.sleep(2)
                continue

            if days_held >= config.XTB_MAX_HOLDING_DAYS:
                print(f"\n[SELL] >>> MAX HOLDING DAYS for {ticker} <<<")
                print(f"       Days held: {days_held} (max: {config.XTB_MAX_HOLDING_DAYS})")
                print(f"       Profit: {profit_pct:.2f}%")
                self.xtb_trader.sell(ticker)
                time.sleep(2)
                continue

            if config.VERBOSE_LOGGING:
                print(f"[INFO] {ticker}: Profit {profit_pct:.2f}% (peak: {peak_profit:.2f}%), days: {days_held}")

    def process_pending_signals(self):
        """Process pending signals and execute on XTB."""
        signals_file = 'trading_signals.json'

        try:
            with open(signals_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()

                if not content:
                    if config.VERBOSE_LOGGING:
                        print(f"[DEBUG] {signals_file} is empty - initialising as []")
                    signals = []
                else:
                    signals = json.loads(content)

        except FileNotFoundError:
            if config.VERBOSE_LOGGING:
                print(f"[DEBUG] {signals_file} not found - creating new file")
            with open(signals_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
            return
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse {signals_file}: {e}")
            print(f"[ERROR] Content: '{content[:100]}...'")
            import shutil
            backup_file = f"{signals_file}.backup"
            shutil.copy(signals_file, backup_file)
            print(f"[INFO] Backup saved to {backup_file}")
            with open(signals_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
            return

        pending = [s for s in signals if s.get('status') == 'PENDING']

        if not pending:
            return

        print(f"\n[INFO] Found {len(pending)} pending signals")

        for signal in pending:
            self.xtb_trader.process_signal(signal)

            with open(signals_file, 'w', encoding='utf-8') as f:
                json.dump(signals, f, ensure_ascii=False, indent=2)

            time.sleep(2)

    def show_stats(self):
        """Print session statistics."""
        print(f"\n{'='*80}")
        print("STATISTICS")
        print("="*80)
        print(f"Signals generated: {len(self.news_monitor.signals)}")
        print(f"AI cost: ${self.news_monitor.sentiment_analyzer.total_cost:.4f}")

        if self.xtb_trader:
            print(f"XTB orders: {len(self.xtb_trader.trade_log)}")


def main():
    """Entry point."""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
