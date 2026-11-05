"""Publish the canonical shared payment views into the portable local report.
Use --check in visual QA to reject manually diverged generated assets.
"""
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
source = root / 'stylist/static/closet-app'
report = root / 'reports/26-11-05/change-log/docs/payment-design'
for origin, destination in [('payment-views.js', 'payment-views.js'), ('payment-views.css', 'style.css')]:
    contents = (source / origin).read_bytes()
    target = report / destination
    if '--check' in sys.argv:
        if not target.exists() or target.read_bytes() != contents:
            raise SystemExit(f'Shared payment view differs: {target}; run scripts/sync_payment_views.py')
    else:
        target.write_bytes(contents)
print('Shared payment view assets match' if '--check' in sys.argv else 'Shared payment view assets synchronized')
