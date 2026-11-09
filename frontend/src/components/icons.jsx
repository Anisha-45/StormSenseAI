const PATHS = {
  home: 'M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10',
  database: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4',
  cluster: 'M12 8a2 2 0 100-4 2 2 0 000 4zM6 20a2 2 0 100-4 2 2 0 000 4zM18 20a2 2 0 100-4 2 2 0 000 4zM12 8v4M12 12l-5 4M12 12l5 4',
  map: 'M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14',
  chart: 'M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-3',
  alert: 'M12 3l10 18H2L12 3zM12 10v4M12 17.5v.5',
  bolt: 'M13 2L4 14h7l-1 8 9-12h-7l1-8z',
  user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 3.6-7 8-7s8 3 8 7',
  mail: 'M3 6h18v12H3zM3 7l9 7 9-7',
  lock: 'M6 11h12v9H6zM8 11V8a4 4 0 118 0v3',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 14.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
  chat: 'M4 5h16v11H9l-5 4V5z',
  file: 'M6 3h8l4 4v14H6V3zM14 3v4h4M9 13h6M9 17h6',
  sliders: 'M4 7h10M18 7h2M4 17h2M10 17h10M14 5v4M6 15v4',
  menu: 'M4 6h16M4 12h16M4 18h16',
  chevron: 'M6 9l6 6 6-6',
  search: 'M11 18a7 7 0 100-14 7 7 0 000 14zM21 21l-5-5',
  route: 'M6 19a2 2 0 100-4 2 2 0 000 4zM18 9a2 2 0 100-4 2 2 0 000 4zM8 17h6a3 3 0 000-6h-4a3 3 0 010-6h6',
  layers: 'M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5',
  clock: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2',
  flag: 'M5 21V4M5 4h11l-2 4 2 4H5',
  box: 'M3 8l9-5 9 5v8l-9 5-9-5V8zM3 8l9 5 9-5M12 13v8',
  users: 'M9 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM2 20c0-3.5 3-6 7-6s7 2.5 7 6M17 5a3 3 0 010 6M19 14c2 .8 3 2.6 3 5',
  x: 'M6 6l12 12M18 6L6 18',
  logout: 'M9 4H5v16h4M16 8l4 4-4 4M20 12H9',
  check: 'M5 12l5 5 9-10',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  info: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 11v5M12 8v.5',
  skull: 'M12 3a8 8 0 00-5 14v3h10v-3a8 8 0 00-5-14zM9.5 11.5h.01M14.5 11.5h.01',
  heart: 'M12 20s-8-5-8-11a4.5 4.5 0 018-2.5A4.5 4.5 0 0120 9c0 6-8 11-8 11z',
  dollar: 'M12 3v18M16 7.5C15 6.5 13.7 6 12 6c-2.2 0-4 1-4 3s1.8 2.7 4 3 4 1 4 3-1.8 3-4 3c-1.7 0-3.3-.6-4.3-1.8',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  pin: 'M12 21s7-6 7-11a7 7 0 10-14 0c0 5 7 11 7 11zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z',
  flask: 'M9 3h6M10 3v6L4.5 19a1.5 1.5 0 001.3 2.2h12.4a1.5 1.5 0 001.3-2.2L14 9V3M7.5 15h9',
}

export function Icon({ name, className = 'h-5 w-5', stroke = 1.8 }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" focusable="false">
      <path d={PATHS[name] || PATHS.info} />
    </svg>
  )
}

export function Logo({ size = 'h-10 w-10', text = true, light = false }) {
  return (
    <span className="inline-flex items-center gap-3">
      <span className={`relative grid ${size} place-items-center rounded-2xl bg-gradient-to-br from-storm-500 via-storm-600 to-ink-800 shadow-lift ring-1 ring-white/30`}>
        <svg viewBox="0 0 32 32" className="h-3/5 w-3/5" aria-hidden="true">
          <path d="M9 19a5 5 0 0 1 1-9.9A6 6 0 0 1 21.6 11 4 4 0 0 1 22 19H9z" fill="#fff" />
          <path d="M15 20l-2 5h3l-1 4 4-6h-3l1-3z" fill="#ffc24a" />
        </svg>
      </span>
      {text && (
        <span className="leading-tight">
          <span className={`block font-display text-lg font-bold tracking-tight ${light ? 'text-white' : 'text-ink-900'}`}>StormSense <span className="text-volt-500">AI</span></span>
          <span className={`block text-[11px] font-medium ${light ? 'text-slate-300' : 'text-slate-500'}`}>Historical weather intelligence</span>
        </span>
      )}
    </span>
  )
}
