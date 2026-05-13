import json
from pathlib import Path

tracker_path = Path('ai_tutor_control/action_planning/task_tracker.json')
tracker = json.loads(tracker_path.read_text(encoding='utf-8'))

# Find and update P2-T06 and P2-T04 statuses
for task in tracker['tasks']:
    if task['id'] == 'P2-T06':
        task['status'] = 'Done'
    elif task['id'] == 'P2-T04':
        task['status'] = 'Done'

# Recalculate summary
done = sum(1 for t in tracker['tasks'] if t['status'] == 'Done')
not_started = sum(1 for t in tracker['tasks'] if t['status'] == 'Not Started')
in_progress = sum(1 for t in tracker['tasks'] if t['status'] == 'In Progress')
total = len(tracker['tasks'])

tracker['summary']['done_tasks'] = done
tracker['summary']['not_started_tasks'] = not_started
tracker['summary']['in_progress_tasks'] = in_progress
tracker['summary']['total_tasks'] = total
tracker['summary']['overall_progress_percent'] = round(100 * done / total) if total > 0 else 0
tracker['last_updated'] = '2026-05-09'

tracker_path.write_text(json.dumps(tracker, indent=2), encoding='utf-8')
print(f'Updated: P2-T06 and P2-T04 marked as Done')
print(f'Progress: {done}/{total} tasks complete ({tracker["summary"]["overall_progress_percent"]}%)')
