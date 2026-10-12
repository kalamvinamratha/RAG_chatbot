import { useState, useRef, useEffect } from 'react';
import type { CompanionKind } from '../lib/companions';

interface CompanionMascotProps {
  kind: CompanionKind;
  size?: 'hero' | 'welcome' | 'avatar';
  thinking?: boolean;
  interactive?: boolean;
}

function playMascotChime(kind: CompanionKind) {
  try {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';

    const freqs: Record<CompanionKind, [number, number]> = {
      general_medicine: [587.33, 880], // D5 -> A5
      cardiology: [523.25, 783.99], // C5 -> G5
      gynaecology: [659.25, 987.77], // E5 -> B5
      neurology: [698.46, 1046.5], // F5 -> C6
    };
    const [f1, f2] = freqs[kind] || [587.33, 880];
    const now = ctx.currentTime;
    osc.frequency.setValueAtTime(f1, now);
    osc.frequency.exponentialRampToValueAtTime(f2, now + 0.12);
    gain.gain.setValueAtTime(0.06, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.35);
  } catch {
    // Audio playback error or autoplay policy safely ignored
  }
}

/** Original, code-native characters: interactive with lively hover and click reactions */
export function CompanionMascot({
  kind,
  size = 'hero',
  thinking = false,
  interactive = true,
}: CompanionMascotProps) {
  const [isLively, setIsLively] = useState(false);
  const [particles, setParticles] = useState<
    Array<{ id: number; symbol: string; dx: number; dy: number }>
  >([]);
  const livelyTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (livelyTimerRef.current) window.clearTimeout(livelyTimerRef.current);
    };
  }, []);

  const handleClick = (e: React.MouseEvent | React.KeyboardEvent) => {
    if (!interactive) return;
    e.stopPropagation();

    // Trigger bouncy lively state
    setIsLively(true);
    if (livelyTimerRef.current) window.clearTimeout(livelyTimerRef.current);
    livelyTimerRef.current = window.setTimeout(() => {
      setIsLively(false);
    }, 950);

    // Spawn lively floating sparkles / medical symbols
    const symbols =
      kind === 'general_medicine'
        ? ['🌿', '✨', '🌱', '🩺', '🌟']
        : kind === 'cardiology'
          ? ['💓', '✨', '🫀', '⚡', '🌟']
          : kind === 'gynaecology'
            ? ['🌸', '✨', '🌷', '🌿', '🌟']
            : ['💡', '✨', '🧠', '⚡', '🌟'];

    const newParticles = Array.from({ length: 4 }).map((_, i) => ({
      id: Date.now() + i,
      symbol: symbols[Math.floor(Math.random() * symbols.length)],
      dx: (Math.random() - 0.5) * 56,
      dy: -(22 + Math.random() * 32),
    }));
    setParticles(newParticles);

    // Play micro-chime
    playMascotChime(kind);
  };

  return (
    <span
      className={`companion-mascot mascot-${kind} mascot-${size}`}
      data-thinking={thinking}
      data-interactive={interactive}
      data-lively={isLively}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (interactive && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          handleClick(e);
        }
      }}
      aria-label={interactive ? `${kind} agent mascot, click for interactive motion` : undefined}
    >
      {/* Floating Sparkles Burst */}
      {isLively && particles.length > 0 && (
        <span className="mascot-sparkle-burst" aria-hidden="true">
          {particles.map((p) => (
            <span
              key={p.id}
              className="mascot-particle"
              style={
                {
                  '--dx': `${p.dx}px`,
                  '--dy': `${p.dy}px`,
                } as React.CSSProperties
              }
            >
              {p.symbol}
            </span>
          ))}
        </span>
      )}

      <svg viewBox="0 0 200 210" fill="none" focusable="false">
        <ellipse className="mascot-ground" cx="100" cy="192" rx="49" ry="8" />
        <g className="mascot-character">
          <g className="mascot-feet">
            <path d="M73 165 Q65 181 80 182 Q92 182 91 167" />
            <path d="M110 167 Q109 182 121 182 Q138 182 129 165" />
          </g>
          <path className="mascot-arm mascot-arm-left" d="M52 119 Q28 109 32 130 Q35 137 44 132" />
          <path
            className="mascot-arm mascot-arm-right"
            d="M148 116 Q171 102 168 125 Q165 134 155 128"
          />
          {kind === 'cardiology' && (
            <>
              <path
                className="mascot-body"
                d="M100 67 C81 34 48 44 45 79 C35 117 48 168 100 174 C153 169 166 121 155 80 C151 44 119 34 100 67Z"
              />
              <path className="mascot-highlight" d="M60 87 Q58 67 75 62" />
              <path className="mascot-emblem" d="M84 142 H94 L99 133 L105 150 L111 142 H121" />
            </>
          )}
          {kind === 'gynaecology' && (
            <>
              <g className="mascot-petals">
                <ellipse cx="100" cy="48" rx="22" ry="26" />
                <ellipse cx="143" cy="76" rx="25" ry="23" transform="rotate(-30 143 76)" />
                <ellipse cx="143" cy="127" rx="25" ry="23" transform="rotate(30 143 127)" />
                <ellipse cx="100" cy="151" rx="22" ry="26" />
                <ellipse cx="57" cy="127" rx="25" ry="23" transform="rotate(-30 57 127)" />
                <ellipse cx="57" cy="76" rx="25" ry="23" transform="rotate(30 57 76)" />
              </g>
              <ellipse className="mascot-body" cx="100" cy="103" rx="49" ry="50" />
              <path className="mascot-highlight" d="M66 86 Q71 69 87 66" />
            </>
          )}
          {kind === 'general_medicine' && (
            <>
              <path
                className="mascot-sprout"
                d="M100 64 Q96 33 76 34 Q72 56 100 57 Q108 28 129 30 Q131 50 100 57"
              />
              <path
                className="mascot-body"
                d="M55 83 C63 56 137 56 145 83 L153 137 C153 182 47 182 47 137Z"
              />
              <path className="mascot-highlight" d="M63 94 Q64 78 79 77" />
              <path className="mascot-emblem" d="M96 139 V155 M88 147 H104" />
            </>
          )}
          {kind === 'neurology' && (
            <>
              <path className="mascot-antenna" d="M78 70 Q60 46 67 35 M122 70 Q141 47 133 35" />
              <circle className="mascot-spark" cx="66" cy="32" r="8" />
              <circle className="mascot-spark" cx="134" cy="32" r="8" />
              <path
                className="mascot-body"
                d="M100 53 C116 52 119 69 133 72 C151 77 148 94 151 108 C167 133 148 145 135 151 C131 174 111 176 100 167 C84 180 67 170 63 151 C42 146 39 129 49 110 C42 93 51 75 68 73 C80 70 81 52 100 53Z"
              />
              <path className="mascot-highlight" d="M64 96 Q64 84 77 82" />
              <path
                className="mascot-emblem"
                d="M100 137 L103 144 L111 147 L103 150 L100 157 L97 150 L89 147 L97 144Z"
              />
            </>
          )}
          <g className="mascot-face">
            <g className="mascot-eyes">
              <ellipse cx="81" cy="108" rx="4" ry="6" />
              <ellipse cx="119" cy="108" rx="4" ry="6" />
            </g>
            <ellipse className="mascot-cheek" cx="69" cy="121" rx="8" ry="4" />
            <ellipse className="mascot-cheek" cx="131" cy="121" rx="8" ry="4" />
            <path className="mascot-smile" d="M92 121 Q100 129 108 121" />
          </g>
        </g>
      </svg>
    </span>
  );
}
