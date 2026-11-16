import os
import re

for root, dirs, files in os.walk('app'):
    for file in files:
        if file.endswith('.py'):
            p = os.path.join(root, file)
            with open(p, 'r', encoding='utf-8') as f:
                c = f.read()
            matches = re.findall(r"current_user\[['\"]([a-zA-Z0-9_]+)['\"]\]", c)
            if matches:
                print(f"{p}: {set(matches)}")
