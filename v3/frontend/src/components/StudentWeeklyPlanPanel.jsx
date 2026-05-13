import React from "react";

export function StudentWeeklyPlanPanel({ studentStudyPlan = null, onPlanAction = null }) {
  if (!studentStudyPlan) return null;

  const hasGoals = !!studentStudyPlan.goal_summary;
  const hasHistory = studentStudyPlan.history?.comparison;
  const hasTargets = Array.isArray(studentStudyPlan.targets) && studentStudyPlan.targets.length > 0;
  const hasSchedule = Array.isArray(studentStudyPlan.schedule) && studentStudyPlan.schedule.length > 0;

  if (!hasGoals && !hasHistory && !hasTargets && !hasSchedule) {
    return null;
  }

  return (
    <div className="role-hub-panel__insights">
      <div className="role-hub-panel__insight-card">
        <strong>Weekly Plan & Goals</strong>

        {hasGoals && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Goal Summary</p>
            <p>{studentStudyPlan.goal_summary}</p>
          </div>
        )}

        {hasHistory && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Previous Week</p>
            <p>
              {studentStudyPlan.history.comparison.summary || `${studentStudyPlan.history.comparison.metric_label}: ${studentStudyPlan.history.comparison.previous_value}`}
            </p>
          </div>
        )}

        {hasTargets && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Week Targets</p>
            {studentStudyPlan.targets.slice(0, 3).map((target) => (
              <div key={target.id || target.label} className="role-hub-panel__insight-card" style={{ marginTop: 8, marginLeft: 0, marginRight: 0 }}>
                <p>
                  {target.label} · {target.current || 0}/{target.target || 0} {target.unit || ""}
                </p>
                <span>{target.completed ? "Done" : "In progress"}</span>
                {target.cta_label && onPlanAction && (
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() => onPlanAction?.(target)}
                    disabled={!onPlanAction}
                  >
                    {target.cta_label}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {hasSchedule && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Schedule</p>
            {studentStudyPlan.schedule.slice(0, 3).map((step) => (
              <div key={step.id || step.title} className="role-hub-panel__insight-card" style={{ marginTop: 8, marginLeft: 0, marginRight: 0 }}>
                <strong>{step.title}</strong>
                <p>{step.description}</p>
                <span>{step.status_label || (step.completed ? "Done" : "Coming up")}</span>
                {step.duration_minutes && <span>{step.duration_minutes} min</span>}
                {step.cta_label && onPlanAction && (
                  <button
                    type="button"
                    className="secondary-button progress-plan-item__action"
                    onClick={() => onPlanAction?.(step)}
                    disabled={!onPlanAction}
                  >
                    {step.cta_label}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
