import React from 'react';
import { readingRatio } from '../utils/gazeUtils';

const CHUNK_WORDS = 65;

// Group prose into ~40-word chunks (at sentence boundaries) — coarser zones are more reliable for gaze.
// Bullet lines stay one zone each.
function parseChunks(text) {
  const result = [];
  const paragraphs = text.split('\n').filter(l => l.trim());

  for (const para of paragraphs) {
    const trimmed = para.trim();
    const isBullet = /^([-•*]|\d+\.)\s/.test(trimmed);

    if (isBullet) {
      result.push({ text: trimmed.replace(/^([-•*]|\d+\.)\s+/, '').trim(), isBullet: true });
    } else {
      const sentences = trimmed.split(/(?<=[.!?])\s+/).filter(Boolean);
      let chunk = '';
      for (const sentence of sentences) {
        const proposed = chunk ? chunk + ' ' + sentence : sentence;
        if (chunk && proposed.split(/\s+/).filter(Boolean).length > CHUNK_WORDS) {
          result.push({ text: chunk.trim(), isBullet: false });
          chunk = sentence;
        } else {
          chunk = proposed;
        }
      }
      if (chunk.trim()) result.push({ text: chunk.trim(), isBullet: false });
    }
  }

  return result;
}

const getHeatBg = (zone, wordCount, zoneLog, heatmapEnabled) => {
  if (!heatmapEnabled) return 'transparent';
  const visits = (zoneLog[zone] || []).length;
  if (visits === 0) return 'transparent';
  const ratio = readingRatio(visits, wordCount);
  if (ratio < 0.5)  return 'rgba(245, 158, 11, 0.35)';   // yellow — skimmed
  if (ratio <= 3.0) return 'rgba(16, 185, 129, 0.45)';    // green  — normal
  return 'rgba(239, 68, 68, 0.45)';                        // red    — confused
};

export default function ResponseDisplay({ text, responseId, zoneLog, heatmapEnabled }) {
  const sentences = parseChunks(text);

  return (
    <div id={`response-${responseId}`} style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
      {sentences.map((s, i) => {
        const zoneId   = `${responseId}:line_${i}`;
        const wordCount = s.text.split(/\s+/).filter(Boolean).length;
        const visits    = (zoneLog[zoneId] || []).length;

        return (
          <div
            key={`${responseId}-${i}`}
            data-zone={zoneId}
            className="gaze-line"
            style={{ backgroundColor: getHeatBg(zoneId, wordCount, zoneLog, heatmapEnabled) }}
          >
            {s.isBullet && <span className="gaze-line-bullet">•</span>}
            <span>{s.text}</span>

            {heatmapEnabled && visits > 0 && (
              <span
                className="gaze-line-visits"
                style={{
                  backgroundColor: visits <= 2
                    ? 'rgba(16,185,129,0.8)'
                    : visits <= 4
                      ? 'rgba(245,158,11,0.8)'
                      : 'rgba(239,68,68,0.8)',
                }}
              >
                {visits}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
