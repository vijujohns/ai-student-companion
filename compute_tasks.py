import json
from pathlib import Path
path = Path('ai_tutor_control/action_planning/task_tracker.json')
tracker = json.loads(path.read_text(encoding='utf-8'))
by_id = {t['id']: t for t in tracker['tasks']}

def is_done(task):
    return task['status'] == 'Done'

unlocked = []
blocked = []
priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
for t in tracker['tasks']:
    if t['status'] != 'Not Started':
        continue
    deps = t.get('dependencies') or []
    blocked_by = [d for d in deps if not is_done(by_id[d])]
    if blocked_by:
        blocked.append((t, blocked_by))
    else:
        unlocked.append(t)

unlocked.sort(key=lambda t: (priority_order.get(t['priority'], 4), t['id']))
blocked.sort(key=lambda x: (priority_order.get(x[0]['priority'], 4), x[0]['id']))
print('UNLOCKED', len(unlocked))
for t in unlocked:
    print(t['id'], '|', t['title'], '|', t['priority'], '| deps', t.get('dependencies'))
print('BLOCKED', len(blocked))
for t, b in blocked:
    print(t['id'], '|', t['title'], '|', t['priority'], '| blocked_by', b)
current_done = {tid for tid, t in by_id.items() if t['status'] == 'Done'}
current_unlocked = {t['id'] for t in unlocked}
next_after = []
for t, b in blocked:
    if all(d in current_done.union(current_unlocked) for d in (t.get('dependencies') or [])):
        next_after.append(t)
next_after.sort(key=lambda t: (priority_order.get(t['priority'], 4), t['id']))
print('NEXT_AFTER', len(next_after))
for t in next_after:
    print(t['id'], '|', t['title'], '|', t['priority'], '| deps', t.get('dependencies'))
