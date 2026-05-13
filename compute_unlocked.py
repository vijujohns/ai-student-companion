import json
from pathlib import Path

tracker_path = Path('ai_tutor_control/action_planning/task_tracker.json')
tracker = json.loads(tracker_path.read_text(encoding='utf-8'))

by_id = {t['id']: t for t in tracker['tasks']}
is_done = lambda tid: by_id[tid]['status'] == 'Done'

unlocked = []
blocked = []

for t in tracker['tasks']:
    if t['status'] != 'Not Started':
        continue
    deps = t.get('dependencies', [])
    blocked_by = [d for d in deps if not is_done(d)]
    if blocked_by:
        blocked.append((t, blocked_by))
    else:
        unlocked.append(t)

priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
unlocked.sort(key=lambda t: (priority_order.get(t['priority'], 4), t['id']))
blocked.sort(key=lambda x: (priority_order.get(x[0]['priority'], 4), x[0]['id']))

print('UNLOCKED TASKS:')
for t in unlocked:
    print(f'{t["id"]} | {t["title"]} | {t["priority"]} | deps: {t.get("dependencies", [])}')

print('\nBLOCKED TASKS:')
for t, b in blocked:
    print(f'{t["id"]} | {t["title"]} | {t["priority"]} | blocked_by: {b}')

# Next after: blocked tasks whose deps are all done or in unlocked
current_unlocked_ids = {t['id'] for t in unlocked}
next_after = []
for t, b in blocked:
    deps = t.get('dependencies', [])
    if all(d in [tid for tid, tt in by_id.items() if tt['status'] == 'Done'] + list(current_unlocked_ids) for d in deps):
        next_after.append(t)
next_after.sort(key=lambda t: (priority_order.get(t['priority'], 4), t['id']))

print('\nNEXT AFTER CURRENT UNLOCKED:')
for t in next_after:
    print(f'{t["id"]} | {t["title"]} | {t["priority"]} | deps: {t.get("dependencies", [])}')
