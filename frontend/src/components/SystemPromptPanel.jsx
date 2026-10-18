import React from 'react';

export default function SystemPromptPanel({ systemPrompt, userProfile }) {
  if (!systemPrompt) {
    return (
      <div style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '12px', color: 'var(--panel-muted)', fontSize: '0.7rem', textAlign: 'center'
      }}>
        System prompt will appear here after your first message.
      </div>
    );
  }

  const lines = systemPrompt.split('\n').filter(l => l.trim());

  const lineColor = (line) => {
    if (line.startsWith('You are') || line.startsWith('Be direct') || line.startsWith('Match'))
      return 'var(--panel-muted)';
    if (line.includes('bullet') || line.includes('prose') || line.includes('Structure'))
      return 'var(--panel-accent)';
    if (line.includes('simple') || line.includes('jargon') || line.includes('short sentences'))
      return 'var(--panel-yellow)';
    if (line.includes('technical') || line.includes('depth') || line.includes('advanced'))
      return 'var(--panel-green)';
    if (line.includes('analogy') || line.includes('real-world') || line.includes('topic'))
      return '#f28b82';
    return 'var(--panel-text)';
  };

  return (
    <div style={{
      height: '100%',
      overflowY: 'auto',
      padding: '8px 10px',
    }}>
      {/* Profile chips */}
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '8px' }}>
        <span style={{
          fontSize: '0.6rem', padding: '2px 7px', borderRadius: '99px',
          background: 'rgba(138,180,248,0.15)', color: 'var(--panel-accent)',
          fontWeight: 600,
        }}>
          complexity {userProfile?.complexity_score ?? 5}/10
        </span>
        <span style={{
          fontSize: '0.6rem', padding: '2px 7px', borderRadius: '99px',
          background: 'rgba(52,168,83,0.15)', color: 'var(--panel-green)',
          fontWeight: 600,
        }}>
          {userProfile?.preferred_format ?? 'prose'}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {lines.map((line, i) => (
          <div
            key={i}
            style={{
              fontSize: '0.62rem',
              lineHeight: '1.55',
              color: lineColor(line),
              borderLeft: i === 0 ? 'none' : `2px solid ${lineColor(line)}30`,
              paddingLeft: i === 0 ? 0 : '6px',
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
