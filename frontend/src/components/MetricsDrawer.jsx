import React, { useState } from 'react';
import { X, TrendingUp, TrendingDown, Minus, RotateCcw } from 'lucide-react';
import { resetDemoProfile } from '../utils/api';

function Sparkline({ history }) {
  if (!history || history.length < 2) return null;
  const W = 160, H = 40, pad = 4;
  const min = -1, max = 1;
  const pts = history.map((v, i) => {
    const x = pad + (i / (history.length - 1)) * (W - pad * 2);
    const y = pad + (1 - (v - min) / (max - min)) * (H - pad * 2);
    return `${x},${y}`;
  });
  const last = history[history.length - 1];
  const prev = history[history.length - 2];
  const trend = last > prev + 0.05 ? 'up' : last < prev - 0.05 ? 'down' : 'flat';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <svg width={W} height={H} style={{ flexShrink: 0 }}>
        {/* zero line */}
        <line
          x1={pad} y1={H / 2} x2={W - pad} y2={H / 2}
          stroke="rgba(255,255,255,0.08)" strokeWidth="1" strokeDasharray="3 3"
        />
        <polyline
          points={pts.join(' ')}
          fill="none"
          stroke={last > 0.3 ? '#81c995' : last >= 0 ? '#fdd663' : '#f28b82'}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* last point dot */}
        {(() => {
          const [lx, ly] = pts[pts.length - 1].split(',').map(Number);
          return (
            <circle cx={lx} cy={ly} r={3}
              fill={last > 0.3 ? '#81c995' : last >= 0 ? '#fdd663' : '#f28b82'} />
          );
        })()}
      </svg>
      {trend === 'up' && <TrendingUp size={14} color="#81c995" />}
      {trend === 'down' && <TrendingDown size={14} color="#f28b82" />}
      {trend === 'flat' && <Minus size={14} color="#fdd663" />}
    </div>
  );
}

function Bar({ value, max = 10, color }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{
        flex: 1, height: '6px', borderRadius: '99px',
        background: 'rgba(255,255,255,0.07)',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: color,
          borderRadius: '99px',
          transition: 'width 0.6s cubic-bezier(0.16,1,0.3,1)',
        }} />
      </div>
      <span style={{ fontSize: '0.9rem', fontWeight: 700, color, minWidth: 24, textAlign: 'right' }}>
        {value}
      </span>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={{ marginBottom: '20px' }}>
      <div style={{
        fontSize: '0.9rem', fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase', color: 'var(--text-muted)',
        marginBottom: '10px',
      }}>
        {label}
      </div>
      {children}
    </div>
  );
}

function Pill({ label, color, bg }) {
  return (
    <span style={{
      fontSize: '0.85rem', fontWeight: 600, padding: '3px 10px',
      borderRadius: '99px', background: bg, color,
    }}>
      {label}
    </span>
  );
}

export default function MetricsDrawer({ open, onClose, userProfile, rewardHistory, onReset }) {
  const [resetting, setResetting] = useState(false);
  const p = userProfile || {};

  const handleReset = async () => {
    setResetting(true);
    try {
      await resetDemoProfile();
      onReset?.();
    } finally {
      setResetting(false);
    }
  };
  const complexity = p.complexity_score ?? 5;
  const complexityColor = complexity >= 7 ? '#81c995' : complexity >= 4 ? '#fdd663' : '#f28b82';

  const flags = p.prospective_flags || [];
  const topics = p.topics_to_simplify || [];
  const comfy  = p.topics_comfortable || [];

  const lastReward = rewardHistory?.length ? rewardHistory[rewardHistory.length - 1] : null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.4)',
          opacity: open ? 1 : 0,
          pointerEvents: open ? 'auto' : 'none',
          transition: 'opacity 0.25s ease',
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0,
        width: '360px',
        background: 'var(--bg-sidebar)',
        borderLeft: '1px solid var(--border)',
        zIndex: 1001,
        display: 'flex', flexDirection: 'column',
        transform: open ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.3s cubic-bezier(0.16,1,0.3,1)',
        boxShadow: open ? '-8px 0 32px rgba(0,0,0,0.35)' : 'none',
      }}>

        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', padding: '16px 20px',
          borderBottom: '1px solid var(--border)', flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              User Metrics
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '1px' }}>
              Live profile — resets each session
            </div>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
            <button
              onClick={handleReset}
              disabled={resetting}
              title="Reset profile to complexity 9 for demo"
              style={{
                background: 'rgba(242,139,130,0.12)', border: '1px solid rgba(242,139,130,0.3)',
                color: '#f28b82', cursor: resetting ? 'default' : 'pointer',
                display: 'flex', alignItems: 'center', gap: '5px',
                padding: '5px 10px', borderRadius: '8px',
                fontSize: '0.75rem', fontWeight: 600,
                opacity: resetting ? 0.6 : 1,
              }}
            >
              <RotateCcw size={13} style={resetting ? { animation: 'spin 1s linear infinite' } : {}} />
              {resetting ? 'Resetting…' : 'Reset Demo'}
            </button>
            <button
              onClick={onClose}
              style={{
                background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '6px', borderRadius: '6px',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>

          <Section label="Cognitive Complexity">
            <Bar value={complexity} max={10} color={complexityColor} />
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '6px' }}>
              {complexity <= 3 && 'Simple language — short sentences, no jargon'}
              {complexity > 3 && complexity <= 6 && 'Moderate depth — some technical terms OK'}
              {complexity > 6 && 'High depth — user comfortable with technical language'}
            </div>
          </Section>

          <Section label="Preferred Format">
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <Pill
                label="Bullet points"
                color={p.preferred_format === 'bullets' ? '#1a73e8' : 'var(--text-muted)'}
                bg={p.preferred_format === 'bullets' ? 'rgba(26,115,232,0.15)' : 'rgba(255,255,255,0.05)'}
              />
              <Pill
                label="Prose"
                color={p.preferred_format === 'prose' ? '#81c995' : 'var(--text-muted)'}
                bg={p.preferred_format === 'prose' ? 'rgba(129,201,149,0.15)' : 'rgba(255,255,255,0.05)'}
              />
            </div>
          </Section>

          <Section label="Reading Behaviour">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Reads to end</span>
                <Pill
                  label={p.reads_to_end ? 'Yes' : 'No'}
                  color={p.reads_to_end ? '#81c995' : '#f28b82'}
                  bg={p.reads_to_end ? 'rgba(129,201,149,0.15)' : 'rgba(242,139,130,0.15)'}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Avg words read</span>
                <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {p.avg_words_read ?? '—'}
                </span>
              </div>
            </div>
          </Section>

          <Section label="Reward History">
            {rewardHistory && rewardHistory.length > 0 ? (
              <div>
                <Sparkline history={rewardHistory} />
                <div style={{ display: 'flex', gap: '6px', marginTop: '10px', flexWrap: 'wrap' }}>
                  {rewardHistory.slice(-8).map((r, i) => (
                    <span key={i} style={{
                      fontSize: '1rem', fontWeight: 700, padding: '2px 7px',
                      borderRadius: '99px',
                      background: r > 0.3 ? 'rgba(129,201,149,0.15)' : r >= 0 ? 'rgba(253,214,99,0.15)' : 'rgba(242,139,130,0.15)',
                      color: r > 0.3 ? '#81c995' : r >= 0 ? '#fdd663' : '#f28b82',
                    }}>
                      {r >= 0 ? '+' : ''}{r.toFixed(2)}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                No turns yet — start chatting
              </div>
            )}
          </Section>

          {flags.length > 0 && (
            <Section label="Active Flags">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {flags.map((f, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '6px 10px', borderRadius: '8px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid var(--border-light)',
                  }}>
                    <span style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>{f.topic}</span>
                    <span style={{
                      fontSize: '0.9rem', fontWeight: 700, padding: '2px 7px',
                      borderRadius: '99px', background: 'rgba(245,158,11,0.15)', color: '#fdd663',
                    }}>
                      {f.action}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {topics.length > 0 && (
            <Section label="Topics to Simplify">
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {topics.map((t, i) => (
                  <Pill key={i} label={t} color="#f28b82" bg="rgba(242,139,130,0.12)" />
                ))}
              </div>
            </Section>
          )}

          {comfy.length > 0 && (
            <Section label="Topics Comfortable">
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {comfy.map((t, i) => (
                  <Pill key={i} label={t} color="#81c995" bg="rgba(129,201,149,0.12)" />
                ))}
              </div>
            </Section>
          )}

        </div>
      </div>
    </>
  );
}
