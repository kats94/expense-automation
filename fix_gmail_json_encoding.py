from pathlib import Path

path = Path(r'C:\Users\m94ka_\expense-automation\gmail_client_secret.json')
text = path.read_text(encoding='utf-8-sig')
path.write_text(text, encoding='utf-8')
print('rewrote', path)
