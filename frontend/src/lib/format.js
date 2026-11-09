export const num = (v, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? '-' : Number(v).toLocaleString(undefined, { maximumFractionDigits: digits })

export const usd = (v) => {
  if (v === null || v === undefined || Number.isNaN(v)) return '-'
  const a = Math.abs(v)
  if (a >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
  if (a >= 1e6) return `$${(v / 1e6).toFixed(2)}M`
  if (a >= 1e3) return `$${(v / 1e3).toFixed(1)}K`
  return `$${Number(v).toFixed(0)}`
}

export const pct = (v, d = 1) => (v === null || v === undefined ? '-' : `${Number(v).toFixed(d)}%`)

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Permissions mirror backend/app/core/security.py. They only decide what to SHOW; the server enforces them.
const PERMS = {
  administrator: ['run_experiments', 'upload_data', 'report_incident', 'review_incidents', 'view_all_incidents', 'manage_resources', 'view_resources', 'manage_tasks', 'view_tasks', 'admin', 'generate_reports'],
  coordinator: ['report_incident', 'review_incidents', 'view_all_incidents', 'manage_resources', 'view_resources', 'manage_tasks', 'view_tasks', 'generate_reports'],
  responder: ['report_incident', 'view_all_incidents', 'view_resources', 'view_tasks'],
  researcher: ['run_experiments', 'upload_data', 'generate_reports'],
  citizen: ['report_incident'],
}
export const can = (user, perm) => !!user && (PERMS[user.role] || []).includes(perm)

// Colour-blind-safe categorical palette.
export const PALETTE = ['#2f7de1', '#e8833a', '#2a9d8f', '#c44e8a', '#8e7cc3', '#d4a72c', '#4d908e', '#b5543c', '#6c757d', '#5b8e3c']
export const clusterColor = (id) => (id === -1 ? '#9aa5b1' : PALETTE[Math.abs(id) % PALETTE.length])
