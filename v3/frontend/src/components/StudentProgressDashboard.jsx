import React from "react";
import { MiniTrendChart } from "./MiniTrendChart";

export function StudentProgressDashboard({ studentProgress = null }) {
  if (!studentProgress) return null;

  const studyTimeMinutes = Math.round(Number(studentProgress.total_study_seconds || 0) / 60);

  return (
    <div className="role-hub-panel__insights">
      <div className="role-hub-panel__insight-card">
        <strong>Study Progress</strong>
        <div className="role-hub-panel__note-actions" style={{ marginTop: 12 }}>
          {studentProgress.total_study_seconds > 0 && (
            <div>
              <span className="progress-pill progress-pill--neutral">
                {studyTimeMinutes} min studied
              </span>
            </div>
          )}
          {typeof studentProgress.streak_days === "number" && (
            <div>
              <span className="progress-pill progress-pill--neutral">
                {studentProgress.streak_days} day streak
              </span>
            </div>
          )}
        </div>

        {Array.isArray(studentProgress.assessment_scores) && studentProgress.assessment_scores.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Assessment trend</p>
            <MiniTrendChart scores={studentProgress.assessment_scores} label="Assessment trend" />
          </div>
        )}
      </div>
    </div>
  );
}
