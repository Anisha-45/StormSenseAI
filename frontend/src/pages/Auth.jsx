import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { ErrorBox } from '../components/ui.jsx'
import { Icon, Logo } from '../components/icons.jsx'

const FEATURES = [
  { icon: 'cluster', title: 'Cluster storms by behaviour', text: 'Hierarchical and DBSCAN clustering with honest quality metrics.' },
  { icon: 'map', title: 'See where and when', text: 'Maps, seasonality, anomalies and multi-hazard hot spots.' },
  { icon: 'shield', title: 'Honest by design', text: 'Historical NOAA records only. Not a forecast or an official warning.' },
]

function Storm() {
  // Deterministic pseudo-random rain so renders are stable.
  const drops = useMemo(() => Array.from({ length: 46 }, (_, i) => ({
    left: (i * 37) % 100,
    delay: ((i * 53) % 140) / 100,
    dur: 0.9 + ((i * 29) % 80) / 100,
    h: 14 + ((i * 17) % 22),
  })), [])
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="absolute -left-24 top-10 h-64 w-96 animate-drift rounded-full bg-storm-500/30 blur-3xl" />
      <div className="absolute -right-16 top-1/3 h-72 w-80 animate-drift rounded-full bg-aqua-500/20 blur-3xl [animation-delay:-6s]" />
      <div className="absolute inset-0 animate-flash bg-white/40" />
      {drops.map((d, i) => (
        <span key={i} className="absolute top-0 w-px animate-rain bg-gradient-to-b from-transparent to-white/60"
          style={{ left: `${d.left}%`, height: d.h, animationDelay: `${d.delay}s`, animationDuration: `${d.dur}s` }} />
      ))}
    </div>
  )
}

function strength(pw) {
  let s = 0
  if (pw.length >= 8) s++
  if (/[a-z]/i.test(pw) && /\d/.test(pw)) s++
  if (pw.length >= 12) s++
  if (/[^a-z0-9]/i.test(pw)) s++
  return s
}

function IconInput({ icon, right, ...props }) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"><Icon name={icon} className="h-[18px] w-[18px]" /></span>
      <input {...props} className={`input !pl-10 ${right ? '!pr-10' : ''}`} />
      {right}
    </div>
  )
}

export default function Auth({ initialMode = 'register' }) {
  const { login, register, continueAsGuest } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState(initialMode)
  const [form, setForm] = useState({ email: '', name: '', password: '', role: 'citizen' })
  const [show, setShow] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const isReg = mode === 'register'
  const sc = strength(form.password)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const err = isReg ? await register(form.email, form.name, form.password, form.role) : await login(form.email, form.password)
    setBusy(false)
    if (err) setError(err)
    else navigate('/')
  }

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* Brand panel */}
      <section className="relative isolate flex flex-1 flex-col justify-between overflow-hidden bg-gradient-to-br from-ink-950 via-ink-800 to-storm-700 p-8 text-white lg:max-w-[52%] lg:p-14">
        <Storm />
        <Logo light />
        <div className="relative my-10 max-w-xl animate-rise">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold text-volt-400">
            <Icon name="bolt" className="h-3.5 w-3.5" /> SIH26078 · NOAA Storm Events
          </span>
          <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.1] tracking-tight lg:text-5xl">
            Understand extreme weather <span className="bg-gradient-to-r from-volt-400 to-aqua-400 bg-clip-text text-transparent">from the data.</span>
          </h1>
          <p className="mt-4 text-base text-slate-300 lg:text-lg">
            An explainable machine-learning workspace that groups historical storm events, flags the unusual ones and shows where they hit.
          </p>
          <ul className="mt-8 grid gap-3">
            {FEATURES.map((f, i) => (
              <li key={f.title} className="glass flex items-start gap-3 rounded-2xl p-4 animate-rise" style={{ animationDelay: `${0.15 * (i + 1)}s` }}>
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/15 text-volt-400"><Icon name={f.icon} /></span>
                <span>
                  <span className="block text-sm font-bold">{f.title}</span>
                  <span className="block text-sm text-slate-300">{f.text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-slate-400">Clustering describes similar past events. It does not predict weather.</p>
      </section>

      {/* Form panel */}
      <section className="flex flex-1 flex-col items-center justify-center bg-[#fff8f0]/70 p-6 lg:p-12">
        <div className="w-full max-w-md">
          <div className="mb-6 flex rounded-2xl bg-white p-1 shadow-soft ring-1 ring-slate-900/5" role="tablist">
            {[['register', 'Sign up'], ['login', 'Sign in']].map(([m, l]) => (
              <button key={m} role="tab" aria-selected={mode === m} type="button" onClick={() => { setMode(m); setError(null) }}
                className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-bold transition ${mode === m ? 'bg-gradient-to-r from-storm-600 to-storm-500 text-white shadow' : 'text-slate-500 hover:text-slate-800'}`}>{l}</button>
            ))}
          </div>

          <form onSubmit={submit} className="card space-y-4 !p-7">
            <div>
              <h2 className="font-display text-2xl font-bold text-ink-900">{isReg ? 'Create your account' : 'Welcome back'}</h2>
              <p className="mt-1 text-sm text-slate-500">{isReg ? 'Sign up to run experiments and save reports.' : 'Sign in to continue to your dashboard.'}</p>
            </div>
            <ErrorBox message={error} />
            {isReg && (
              <label className="block"><span className="label">Full name</span>
                <IconInput icon="user" required minLength={2} value={form.name} onChange={set('name')} autoComplete="name" placeholder="Your name" />
              </label>
            )}
            <label className="block"><span className="label">Email</span>
              <IconInput icon="mail" type="email" required value={form.email} onChange={set('email')} autoComplete="email" placeholder="you@example.com" />
            </label>
            <label className="block"><span className="label">Password</span>
              <IconInput icon="lock" type={show ? 'text' : 'password'} required minLength={isReg ? 8 : 1} value={form.password} onChange={set('password')}
                autoComplete={isReg ? 'new-password' : 'current-password'} placeholder={isReg ? 'At least 8 characters' : 'Your password'}
                right={<button type="button" onClick={() => setShow((s) => !s)} aria-label={show ? 'Hide password' : 'Show password'} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"><Icon name="eye" className="h-[18px] w-[18px]" /></button>} />
              {isReg && (
                <>
                  <div className="mt-2 flex gap-1" aria-hidden="true">
                    {[0, 1, 2, 3].map((i) => <span key={i} className={`h-1.5 flex-1 rounded-full ${i < sc ? ['bg-red-400', 'bg-orange-400', 'bg-yellow-400', 'bg-emerald-500'][sc - 1] : 'bg-slate-200'}`} />)}
                  </div>
                  <span className="mt-1 block text-xs text-slate-500">Use 8+ characters with letters and digits.</span>
                </>
              )}
            </label>
            {isReg && (
              <label className="block"><span className="label">I am a</span>
                <select className="input" value={form.role} onChange={set('role')}>
                  <option value="citizen">Citizen</option>
                  <option value="researcher">Researcher / analyst / student</option>
                </select>
                <span className="mt-1 block text-xs text-slate-500">Staff roles (coordinator, responder, administrator) are assigned by an administrator.</span>
              </label>
            )}
            <button className="btn-accent w-full !py-3" disabled={busy}>
              {busy ? 'Please wait...' : isReg ? 'Create account' : 'Sign in'} {!busy && <Icon name="arrow" className="h-4 w-4" />}
            </button>
            <p className="text-center text-sm text-slate-500">
              {isReg ? 'Already registered?' : 'New here?'}{' '}
              <button type="button" className="font-bold text-storm-700 hover:underline" onClick={() => { setMode(isReg ? 'login' : 'register'); setError(null) }}>
                {isReg ? 'Sign in' : 'Create an account'}
              </button>
            </p>
          </form>

          <button type="button" className="mx-auto mt-5 flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-storm-700"
            onClick={() => { continueAsGuest(); navigate('/') }}>
            Continue as guest (read-only analytics) <Icon name="arrow" className="h-4 w-4" />
          </button>
        </div>
      </section>
    </div>
  )
}
