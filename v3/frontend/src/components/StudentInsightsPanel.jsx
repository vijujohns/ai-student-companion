import React from "react";

export function StudentInsightsPanel({ studentInsights = null, onPlanAction = null }) {
  if (!studentInsights) return null;

  const hasHeadlines = Array.isArray(studentInsights.headlines) && studentInsights.headlines.length > 0;
  const hasNotifications = Array.isArray(studentInsights.notifications) && studentInsights.notifications.length > 0;
  const hasRecommendations = Array.isArray(studentInsights.recommendations) && studentInsights.recommendations.length > 0;
  const hasBadges = Array.isArray(studentInsights.badges) && studentInsights.badges.length > 0;

  if (!hasHeadlines && !hasNotifications && !hasRecommendations && !hasBadges) {
    return null;
  }

  return (
    <div className="role-hub-panel__insights">
      <div className="role-hub-panel__insight-card">
        <strong>Coaching Insights</strong>

        {hasHeadlines && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Headlines</p>
            {studentInsights.headlines.slice(0, 2).map((headline, idx) => (
              <p key={idx} style={{ marginTop: 6 }}>
                {headline}
              </p>
            ))}
          </div>
        )}

        {hasNotifications && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Notifications</p>
            {studentInsights.notifications.slice(0, 2).map((notification, idx) => (
              <div key={idx} style={{ marginTop: 6 }}>
                <p>{notification.message}</p>
                {notification.severity && (
                  <span className={`progress-pill progress-pill--${notification.severity}`}>
                    {notification.severity}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {hasRecommendations && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Recommendations</p>
            {studentInsights.recommendations.slice(0, 2).map((recommendation, idx) => (
              <div key={idx} style={{ marginTop: 6 }}>
                <p>{recommendation.title || recommendation.text}</p>
                {recommendation.cta_label && onPlanAction && (
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => onPlanAction?.(recommendation)}
                  >
                    {recommendation.cta_label}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {hasBadges && (
          <div style={{ marginTop: 12 }}>
            <p className="sidebar-note">Badges & Achievements</p>
            <div className="role-hub-panel__note-actions">
              {studentInsights.badges.slice(0, 2).map((badge, idx) => (
                <span key={idx} className="progress-pill progress-pill--neutral">
                  {badge.label || badge.name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
