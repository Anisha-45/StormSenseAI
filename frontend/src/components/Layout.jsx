import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { GROUPS, NAV, RAIL } from '../lib/nav.js'
import { Icon, Logo } from './icons.jsx'

const linkCls = ({ isActive }) =>
  `flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition ${isActive ? 'bg-storm-50 text-storm-700' : 'text-slate-600 hover:bg-slate-50 hover:text-ink-900'}`

function GroupMenu({ group, open, onToggle, onClose }) {
  const items = NAV.filter((n) => n.group === group)
  return (
    <div className="relative">
      <button type="button" aria-haspopup="true" aria-expanded={open} onClick={onToggle}
        className={`flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold transition ${open ? 'bg-storm-50 text-storm-700' : 'text-slate-600 hover:text-storm-700'}`}>
        {group}
        <Icon name="chevron" className={`h-4 w-4 transition ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-[1200] mt-2 w-64 rounded-2xl bg-white p-2 shadow-lift ring-1 ring-slate-900/10 animate-rise">
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} onClick={onClose} className={linkCls}>
              <Icon name={n.icon} className="h-[18px] w-[18px]" />{n.label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

function UserMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const initials = (user.name || user.email || '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase()
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="true" aria-expanded={open}
        className="flex items-center gap-3 rounded-full bg-white py-1 pl-3 pr-1 shadow-sm ring-1 ring-slate-900/10 transition hover:shadow-md">
        <span className="hidden text-right leading-tight sm:block">
          <span className="block text-sm font-bold text-ink-900">{user.name}</span>
          <span className="block text-[11px] font-semibold capitalize text-storm-600">{user.role}</span>
        </span>
        <span className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-volt-400 to-volt-600 text-sm font-extrabold text-ink-950">{initials}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full z-[1200] mt-2 w-56 rounded-2xl bg-white p-2 shadow-lift ring-1 ring-slate-900/10 animate-rise">
          <div className="px-3 py-2 text-xs text-slate-500">{user.email}</div>
          <Link to="/settings" onClick={() => setOpen(false)} className={linkCls({ isActive: false })}><Icon name="sliders" className="h-[18px] w-[18px]" />Settings</Link>
          <button type="button" onClick={onLogout} className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50">
            <Icon name="logout" className="h-[18px] w-[18px]" />Sign out
          </button>
        </div>
      )}
    </div>
  )
}

function Footer() {
  const year = new Date().getFullYear()
  return (
    <footer className="mt-10 bg-gradient-to-br from-ink-950 via-ink-900 to-ink-800 text-slate-300">
      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-10 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo light />
          <p className="mt-4 max-w-md text-sm text-slate-400">
            Explainable clustering and analytics over NOAA Storm Events. Built for SIH26078 using hierarchical agglomerative clustering and DBSCAN.
          </p>
        </div>
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-volt-400">Explore</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {['/clustering', '/geography', '/anomalies', '/similar'].map((to) => (
              <li key={to}><Link className="hover:text-white" to={to}>{NAV.find((n) => n.to === to).label}</Link></li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-volt-400">Resources</h3>
          <ul className="mt-3 space-y-2 text-sm">
            {['/quality', '/reports', '/assistant', '/settings'].map((to) => (
              <li key={to}><Link className="hover:text-white" to={to}>{NAV.find((n) => n.to === to).label}</Link></li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-6 py-4 text-xs text-slate-400 md:flex-row md:items-center md:justify-between">
          <span>© {year} StormSense AI. Data: NOAA Storm Events (project extract).</span>
          <span className="max-w-xl md:text-right">Historical records only. Not a forecast, not an official warning. For emergencies contact local authorities and the National Weather Service.</span>
        </div>
      </div>
    </footer>
  )
}

export default function Layout() {
  const { user, ready, guest, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [drawer, setDrawer] = useState(false)
  const [menu, setMenu] = useState(null)
  const [banner, setBanner] = useState(true)
  const headerRef = useRef(null)

  useEffect(() => { setDrawer(false); setMenu(null) }, [location.pathname])
  useEffect(() => {
    const h = (e) => { if (headerRef.current && !headerRef.current.contains(e.target)) setMenu(null) }
    const k = (e) => { if (e.key === 'Escape') { setMenu(null); setDrawer(false) } }
    document.addEventListener('mousedown', h)
    document.addEventListener('keydown', k)
    return () => { document.removeEventListener('mousedown', h); document.removeEventListener('keydown', k) }
  }, [])

  if (!ready) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Loading...</div>
  if (!user && !guest) return <Navigate to="/signup" replace />

  const rail = RAIL.map((to) => NAV.find((n) => n.to === to))

  return (
    <div className="flex min-h-screen flex-col">
      {banner && (
        <div className="relative bg-gradient-to-r from-volt-500 via-volt-400 to-volt-500 px-10 py-2 text-center text-xs font-bold text-ink-950 sm:text-sm">
          <Icon name="info" className="mr-1.5 inline h-4 w-4 align-[-3px]" />
          Historical NOAA records only. This is not a forecast or an official warning.
          <button type="button" aria-label="Dismiss notice" onClick={() => setBanner(false)} className="absolute right-3 top-1/2 -translate-y-1/2 rounded p-1 hover:bg-black/10"><Icon name="x" className="h-4 w-4" /></button>
        </div>
      )}

      <header ref={headerRef} className="sticky top-0 z-[1100] border-b border-white/60 bg-white/85 backdrop-blur-xl">
        <div className="flex items-center gap-3 px-4 py-2.5 lg:px-6">
          <button type="button" className="btn-secondary !px-2.5 lg:hidden" aria-label="Open navigation" onClick={() => setDrawer(true)}><Icon name="menu" /></button>
          <Link to="/" aria-label="StormSense AI home"><Logo size="h-10 w-10" /></Link>
          <nav aria-label="Main navigation" className="ml-6 hidden items-center gap-1 lg:flex">
            {GROUPS.filter((g) => g !== 'Account').map((g) => (
              <GroupMenu key={g} group={g} open={menu === g} onToggle={() => setMenu(menu === g ? null : g)} onClose={() => setMenu(null)} />
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {user ? (
              <UserMenu user={user} onLogout={() => { logout(); navigate('/signup') }} />
            ) : (
              <>
                <span className="hidden rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600 sm:inline">Guest · read-only</span>
                <button className="btn" onClick={() => { logout(); navigate('/signup') }}>Sign up</button>
              </>
            )}
          </div>
        </div>
      </header>

      {drawer && (
        <div className="fixed inset-0 z-[1300] lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink-950/60 backdrop-blur-sm" onClick={() => setDrawer(false)} />
          <aside className="scroll-thin relative h-full w-80 max-w-[85%] overflow-y-auto bg-white p-4 shadow-lift animate-rise">
            <div className="mb-3 flex items-center justify-between"><Logo size="h-9 w-9" /><button type="button" aria-label="Close navigation" className="btn-secondary !px-2" onClick={() => setDrawer(false)}><Icon name="x" /></button></div>
            {GROUPS.map((g) => (
              <div key={g} className="mt-3">
                <div className="px-3 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">{g}</div>
                {NAV.filter((n) => n.group === g).map((n) => (
                  <NavLink key={n.to} to={n.to} end={n.end} className={linkCls}><Icon name={n.icon} className="h-[18px] w-[18px]" />{n.label}</NavLink>
                ))}
              </div>
            ))}
          </aside>
        </div>
      )}

      <div className="flex flex-1">
        <aside className="sticky top-[60px] hidden h-[calc(100vh-60px)] w-[84px] shrink-0 flex-col items-stretch gap-1 bg-gradient-to-b from-ink-900 to-ink-800 py-4 lg:flex" aria-label="Quick links">
          {rail.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} title={n.label}
              className={({ isActive }) => `group relative mx-2 flex flex-col items-center gap-1 rounded-xl px-1 py-2.5 text-[11px] font-semibold leading-tight transition ${isActive ? 'bg-white/15 text-white' : 'text-slate-400 hover:bg-white/10 hover:text-white'}`}>
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute -left-2 top-2 h-[calc(100%-16px)] w-1 rounded-r-full bg-volt-400" />}
                  <Icon name={n.icon} className={`h-6 w-6 ${isActive ? 'text-volt-400' : ''}`} />
                  <span className="text-center">{n.label.split(' ')[0]}</span>
                </>
              )}
            </NavLink>
          ))}
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6 lg:p-8"><Outlet /></main>
        </div>
      </div>
      <Footer />
    </div>
  )
}
