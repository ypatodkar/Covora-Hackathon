import React, { useRef } from 'react';

export default function GazeMirror({ messages, currentLineId }) {
  const containerRef = useRef(null);

  // Find the last assistant message
  const lastAI = [...messages].reverse().find(m => m.role === 'assistant');

  if (!lastAI || lastAI.responseId === 'init') {
    return (
      <div style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '12px', color: 'var(--panel-muted)', fontSize: '0.7rem', textAlign: 'center'
      }}>
        Waiting for a response to track…
      </div>
    );
  }

  const lines = lastAI.text
    .split('\n')
    .map(p => p.trim())
    .filter(p => p.length > 0);

  return (
    <div
      ref={containerRef}
      style={{
        height: '100%',
        overflowY: 'auto',
        padding: '8px 10px',
        fontSize: '0.62rem',
        lineHeight: '1.6',
        color: 'var(--panel-text)',
        wordBreak: 'break-word',
      }}
    >
      {lines.map((line, i) => {
        const lineId = `${lastAI.responseId}:line_${i}`;
        const isActive = currentLineId === lineId;
        const isBullet = line.startsWith('•') || line.startsWith('-') || line.startsWith('*') || /^\d+\./.test(line);
        const cleanText = isBullet ? line.replace(/^([-•*]\s*|\d+\.\s*)/, '').trim() : line;

        return (
          <p
            key={lineId}
            style={{
              margin: '0 0 4px 0',
              display: 'flex',
              gap: '3px',
              backgroundColor: isActive ? 'rgba(138,180,248,0.45)' : 'transparent',
              borderRadius: '3px',
              padding: '1px 2px',
              color: isActive ? '#fff' : 'var(--panel-text)',
              transition: 'background-color 0.15s',
            }}
          >
            {isBullet && <span style={{ color: 'var(--panel-accent)', marginRight: '3px', flexShrink: 0 }}>•</span>}
            <span>{cleanText}</span>
          </p>
        );
      })}
    </div>
  );
}
