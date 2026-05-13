import React from "react";

export function MiniTrendChart({ scores = [], label = "Assessment trend" }) {
  if (!Array.isArray(scores) || scores.length < 2) return null;
  const safeScores = scores.map((value) => Math.max(0, Math.min(100, Number(value) || 0)));
  const width = 120;
  const height = 32;
  const stepX = safeScores.length > 1 ? width / (safeScores.length - 1) : width;
  const points = safeScores
    .map((score, index) => {
      const x = Math.round(index * stepX);
      const y = Math.round(height - (score / 100) * (height - 4) - 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg role="img" aria-label={label} width="120" height="32" viewBox={`0 0 ${width} ${height}`}>
      <polyline fill="none" stroke="#6c63ff" strokeWidth="2" points={points} />
    </svg>
  );
}
