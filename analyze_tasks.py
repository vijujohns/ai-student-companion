import json

# Load tracker
with open(r'd:\GPT\ai-student-companion\ai_tutor_control\action_planning\task_tracker.json') as f:
    data = json.load(f)

tasks = {t['id']: t for t in data['tasks']}

# Find unlocked tasks (Not Started + all deps Done)
unlocked = []
blocked = {}

for task_id, task in tasks.items():
    if task['status'] != 'Not Started':
        continue
    
    deps = task.get('dependencies', [])
    all_done = all(tasks[dep]['status'] == 'Done' for dep in deps)
    
    if all_done:
        unlocked.append((task_id, task))
    else:
        blocked_by = [dep for dep in deps if tasks[dep]['status'] != 'Done']
        blocked[task_id] = blocked_by

# Sort by priority
priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
unlocked.sort(key=lambda x: (priority_order.get(x[1]['priority'], 999), x[0]))

print("=" * 80)
print("UNLOCKED TASKS (Ready Now)")
print("=" * 80)
for task_id, task in unlocked[:10]:  # Top 10
    print(f"\n{task_id} [{task['priority']}] - {task['title']}")
    print(f"  Phase: {task['phase']}")
    print(f"  Effort: {task['estimated_effort']}")

print("\n" + "=" * 80)
print(f"BLOCKED TASKS (Top 5)")
print("=" * 80)
for i, (task_id, blocked_by) in enumerate(list(blocked.items())[:5]):
    task = tasks[task_id]
    print(f"\n{task_id} - {task['title']}")
    print(f"  Blocked by: {', '.join(blocked_by)}")

print(f"\n\n{'=' * 80}")
print(f"SUMMARY: {len(unlocked)} unlocked, {len(blocked)} blocked")
print(f"Done: {sum(1 for t in tasks.values() if t['status']=='Done')}/43")
