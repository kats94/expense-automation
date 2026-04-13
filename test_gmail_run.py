#!/usr/bin/env python3

import sys
sys.path.insert(0, r'C:\Users\m94ka_\expense-automation')

try:
    from gmail_integration import main
    print("Starting Gmail integration...")
    main()
    print("Gmail integration completed successfully!")
except Exception as e:
    print(f"Error occurred: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
