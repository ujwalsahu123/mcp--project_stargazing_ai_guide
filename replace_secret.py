#!/usr/bin/env python3
import os
secret = b'[REDACTED]'
replacement = b'[REDACTED]'
for root, dirs, files in os.walk('.'):
    if '.git' in root.split(os.sep):
        continue
    for fname in files:
        path = os.path.join(root, fname)
        try:
            with open(path, 'rb') as f:
                data = f.read()
            if secret in data:
                new = data.replace(secret, replacement)
                with open(path, 'wb') as f:
                    f.write(new)
        except Exception:
            pass
