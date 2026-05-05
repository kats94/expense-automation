"""月末チェック付き fixed_costs.py 起動ラッパー。

スケジュール実行（GitHub Actions cron）:
  python run_monthly_fixed_costs.py
  → 当日が月末でなければスキップ。月末なら当月を処理。

手動実行（テスト・バックフィル用）:
  python run_monthly_fixed_costs.py --month 4 --year 2026
  → 月末チェックをスキップして指定月を処理。
"""

import argparse
import calendar
import sys
from datetime import datetime

from fixed_costs import main


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", type=int, default=None, help="対象月 (1-12)。省略時は当月を月末チェック付きで処理。")
    parser.add_argument("--year", type=int, default=None, help="対象年。省略時は当年。")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    now = datetime.now()

    if args.month is not None:
        # 月を明示指定 → 月末チェックなしで実行（テスト・バックフィル用）
        target_month = args.month
        target_year = args.year or now.year
        print(f"手動実行: {target_year}年{target_month}月のデータを処理します（月末チェックをスキップ）。")
    else:
        # 月末チェック（スケジュール実行）
        last_day = calendar.monthrange(now.year, now.month)[1]
        if now.day != last_day:
            print(f"{now.strftime('%Y-%m-%d')} は月末ではないためスキップします（今月末: {now.year}/{now.month}/{last_day}）。")
            sys.exit(0)
        target_month = now.month
        target_year = now.year
        print(f"{now.strftime('%Y-%m-%d')} は月末です。{target_year}年{target_month}月の固定費を処理します。")

    main(target_month=target_month, target_year=target_year)
