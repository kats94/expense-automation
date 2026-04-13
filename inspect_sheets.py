#!/usr/bin/env python3

from google_auth import get_sheets_service, get_spreadsheet_config
import json

service = get_sheets_service()
spreadsheet_id, sheet_name = get_spreadsheet_config()

# Get spreadsheet metadata
spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

print("Spreadsheet title:", spreadsheet['properties']['title'])
print("\nSheets available:")
for sheet in spreadsheet['sheets']:
    print(f"  - Sheet name: {sheet['properties']['title']}")
    print(f"    Sheet ID: {sheet['properties']['sheetId']}")
    print(f"    Grid rows: {sheet['properties']['gridProperties'].get('rowCount', 'N/A')}")
    print(f"    Grid columns: {sheet['properties']['gridProperties'].get('columnCount', 'N/A')}")
