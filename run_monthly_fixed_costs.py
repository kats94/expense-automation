"""月末チェック付き fixed_costs.py 起動ラッパー。
Render cron は「59 23 28-31 * *」で毎月28〜31日に起動するため、
実行日が実際にその月の最終日かを確認してから処理を実行する。
"""

import calendar
import sys
from datetime import datetime

from fixed_costs import main

if __name__ == "__main__":
    now = datetime.now()
    last_day = calendar.monthrange(now.year, now.month)[1]
    if now.day != last_day:
        print(f"{now.strftime('%Y-%m-%d')} は月末ではないためスキップします（月末: {last_day}日）。")
        sys.exit(0)

    print(f"{now.strftime('%Y-%m-%d')} は月末です。固定費の自動入力を開始します。")
    main()
