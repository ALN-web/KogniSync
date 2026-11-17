/** Small metallic SVG illustrations for the capability cards (no stock photos needed). */
const O = "#ff5a2c";

function Frame({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 240 120" role="presentation" aria-hidden="true" className="ill">
      <defs>
        <linearGradient id={`bg-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2a2d33" />
          <stop offset="0.55" stopColor="#17191d" />
          <stop offset="1" stopColor="#0e0f12" />
        </linearGradient>
        <linearGradient id={`steel-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e8ebef" />
          <stop offset="0.5" stopColor="#8f97a1" />
          <stop offset="1" stopColor="#4a5058" />
        </linearGradient>
        <radialGradient id={`glow-${id}`} cx="0.75" cy="0.8" r="0.6">
          <stop offset="0" stopColor={O} stopOpacity="0.35" />
          <stop offset="1" stopColor={O} stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="240" height="120" fill={`url(#bg-${id})`} />
      <rect width="240" height="120" fill={`url(#glow-${id})`} />
      {children}
    </svg>
  );
}

export function OrchestrateArt() {
  const stops = [24, 64, 104, 144, 184, 216];
  return (
    <Frame id="orc">
      <path d="M24 78 C 60 20, 110 20, 144 54 S 200 96, 216 50" fill="none" stroke={O} strokeWidth="2" strokeDasharray="5 5" />
      {stops.map((x, i) => (
        <g key={x}>
          <circle cx={x} cy={[78, 40, 33, 54, 80, 50][i]} r="9" fill="url(#steel-orc)" />
          <circle cx={x} cy={[78, 40, 33, 54, 80, 50][i]} r="3" fill={i === 0 || i === 5 ? O : "#16181c"} />
        </g>
      ))}
    </Frame>
  );
}

export function OptimizeArt() {
  const dots = [
    [40, 30], [62, 52], [90, 66], [128, 80], [176, 88], [70, 34], [110, 48], [150, 62], [196, 70], [120, 30], [168, 40],
  ];
  const front = [[40, 30], [62, 52], [90, 66], [128, 80], [176, 88]];
  return (
    <Frame id="opt">
      <line x1="28" y1="100" x2="220" y2="100" stroke="#5a616b" />
      <line x1="28" y1="100" x2="28" y2="16" stroke="#5a616b" />
      <polyline points={front.map((p) => p.join(",")).join(" ")} fill="none" stroke={O} strokeWidth="2" />
      {dots.map(([x, y]) => {
        const onFront = front.some(([a, b]) => a === x && b === y);
        return <circle key={`${x}-${y}`} cx={x} cy={y} r={onFront ? 5 : 3.5} fill={onFront ? O : "url(#steel-opt)"} />;
      })}
    </Frame>
  );
}

export function TrustArt() {
  const rows = [
    ["LIVE", "#3ddc84"],
    ["SCHEDULED", "#8ab4f8"],
    ["ESTIMATED", "#ffb020"],
  ];
  return (
    <Frame id="tru">
      {rows.map(([label, color], i) => (
        <g key={label} transform={`translate(30 ${22 + i * 30})`}>
          <rect width="120" height="20" rx="4" fill="url(#steel-tru)" opacity="0.18" />
          <rect width="58" height="20" rx="4" fill="none" stroke={color} />
          <text x="29" y="14" textAnchor="middle" fontSize="8" fontFamily="monospace" fill={color}>
            {label}
          </text>
          <rect x="70" y="7" width={[44, 36, 28][i]} height="6" rx="3" fill="#c9ced6" opacity="0.6" />
        </g>
      ))}
      <circle cx="196" cy="60" r="26" fill="none" stroke="url(#steel-tru)" strokeWidth="6" />
      <path d="M184 60 l9 9 l17 -19" fill="none" stroke={O} strokeWidth="4" strokeLinecap="round" />
    </Frame>
  );
}

export function BookArt() {
  return (
    <Frame id="bok">
      <rect x="34" y="20" width="120" height="80" rx="8" fill="url(#steel-bok)" />
      <rect x="44" y="30" width="56" height="8" rx="2" fill="#2a2d33" />
      <rect x="44" y="46" width="80" height="5" rx="2" fill="#4a5058" />
      <rect x="44" y="58" width="64" height="5" rx="2" fill="#4a5058" />
      <rect x="44" y="76" width="40" height="12" rx="3" fill={O} />
      <g transform="translate(164 30)">
        <rect width="54" height="54" rx="6" fill="#f2f3f5" />
        {Array.from({ length: 25 }, (_, i) => (i * 7 + 3) % 3 !== 0 && (
          <rect key={i} x={6 + (i % 5) * 9} y={6 + Math.floor(i / 5) * 9} width="7" height="7" fill="#16181c" />
        ))}
      </g>
    </Frame>
  );
}

export function ProtectArt() {
  const xs = [26, 74, 122, 170, 214];
  return (
    <Frame id="pro">
      {xs.slice(0, -1).map((x, i) => (
        <line key={x} x1={x} y1="70" x2={xs[i + 1]} y2="70" stroke={i === 1 ? O : "#8f97a1"} strokeWidth="3" strokeDasharray={i === 1 ? "4 5" : undefined} />
      ))}
      <path d="M74 70 C 96 18, 150 18, 170 70" fill="none" stroke={O} strokeWidth="2.5" />
      {xs.map((x, i) => (
        <circle key={x} cx={x} cy="70" r="8" fill={i === 2 ? "#16181c" : "url(#steel-pro)"} stroke={i === 2 ? O : "none"} strokeWidth="2" />
      ))}
      <text x="122" y="100" textAnchor="middle" fontSize="9" fontFamily="monospace" fill={O}>
        DELAYED 90 MIN
      </text>
    </Frame>
  );
}

export function ConverseArt() {
  const bars = [8, 18, 30, 14, 36, 22, 10, 26, 40, 20, 12, 30, 16, 8];
  return (
    <Frame id="con">
      <rect x="24" y="22" width="110" height="34" rx="12" fill="url(#steel-con)" />
      <rect x="36" y="34" width="70" height="5" rx="2" fill="#2a2d33" />
      <rect x="36" y="43" width="48" height="5" rx="2" fill="#2a2d33" />
      <rect x="96" y="66" width="120" height="34" rx="12" fill={O} opacity="0.9" />
      <text x="156" y="87" textAnchor="middle" fontSize="11" fill="#fff">
        नमस्ते · ನಮಸ್ಕಾರ
      </text>
      {bars.map((h, i) => (
        <rect key={i} x={150 + i * 6} y={40 - h / 2} width="3" height={h} rx="1.5" fill="#c9ced6" opacity="0.7" />
      ))}
    </Frame>
  );
}
