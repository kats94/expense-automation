"""N列（合計列）の「USD ... = JPY XXXX」文字列を =SUM(B:M) 数式に一括修正するスクリプト。"""

import re
from fixed_costs import load_sheet_data, update_sheet_values
from google_auth import get_spreadsheet_config


def is_memo_string(text: str) -> bool:
    return isinstance(text, str) and ("JPY" in text or "@" in text)


def main():
    spreadsheet_id, sheet_name = get_spreadsheet_config("fixed_cost_sheet_name")
    values = load_sheet_data(spreadsheet_id, sheet_name)

    updates = []
    # N列はインデックス 13
    N_COL_IDX = 13
    for row_idx, row in enumerate(values, start=1):
        if N_COL_IDX >= len(row):
            continue
        cell = row[N_COL_IDX]
        if not is_memo_string(cell):
            continue

        item_name = row[0] if row else ""
        formula = f"=SUM(B{row_idx}:M{row_idx})"
        range_str = f"'{sheet_name}'!N{row_idx}"
        updates.append({"range": range_str, "values": [formula]})
        print(f"  修正: {item_name} [N{row_idx}] {cell!r} → {formula}")

    if not updates:
        print("修正対象のセルは見つかりませんでした。")
        return

    print(f"\n{len(updates)} セルを更新します...")
    update_sheet_values(spreadsheet_id, updates)
    print("完了。")


if __name__ == "__main__":
    main()
