"""FY26 Q1（1〜3月）の Genspark・Claude・ChatGPT 固定費をバックフィルするスクリプト。"""

from fixed_costs import (
    get_12th_exchange_rate,
    get_spreadsheet_config,
    load_config,
    load_sheet_data,
    process_invoice,
    update_fixed_cost_item,
)

EXCHANGE_API_KEY = "bdfb9b547a9db8623799be66"
TARGET_YEAR = 2026
TARGET_MONTHS = [1, 2, 3]

INVOICE_ITEMS = [
    {
        "sender": "invoice+statements+acct_1Q2SePHy7UpDvrVi@stripe.com",
        "item_name": "Genspark",
        "currency": "USD",
    },
    {
        "sender": "invoice+statements@mail.anthropic.com",
        "item_name": "Claude",
        "currency": "USD",
    },
]

MONTH_NAMES = {1: "1月", 2: "2月", 3: "3月"}


def main():
    load_config()
    spreadsheet_id, sheet_name = get_spreadsheet_config("fixed_cost_sheet_name")

    for month in TARGET_MONTHS:
        print(f"\n=== {MONTH_NAMES[month]} の処理 ===")

        rate = get_12th_exchange_rate(EXCHANGE_API_KEY, base="USD", target="JPY", year=TARGET_YEAR, month=month)
        print(f"為替レート ({TARGET_YEAR}/{month:02d}/12): {rate:.6f} JPY/USD")

        for invoice in INVOICE_ITEMS:
            try:
                print(f"処理開始: {invoice['item_name']}")
                process_invoice(
                    spreadsheet_id,
                    sheet_name,
                    invoice["sender"],
                    invoice["item_name"],
                    invoice["currency"],
                    EXCHANGE_API_KEY,
                    exchange_rate_12th=rate,
                    target_month=month,
                    target_year=TARGET_YEAR,
                )
                print(f"処理完了: {invoice['item_name']}")
            except Exception as exc:
                print(f"{invoice['item_name']} の処理中にエラーが発生しました: {exc}")

        # ChatGPT: $22 固定
        chatgpt_amount = str(round(22 * rate))
        chatgpt_memo = f"USD 22 @ {rate:.6f} = JPY {chatgpt_amount}"
        values = load_sheet_data(spreadsheet_id, sheet_name)
        update_fixed_cost_item(
            spreadsheet_id,
            sheet_name,
            values,
            "ChatGPT",
            chatgpt_amount,
            chatgpt_memo,
            target_month=month,
        )
        print(f"ChatGPT を {chatgpt_amount} 円で更新しました。({chatgpt_memo})")

    print("\nQ1 バックフィル完了。")


if __name__ == "__main__":
    main()
