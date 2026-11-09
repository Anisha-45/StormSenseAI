// Single source of truth for navigation: used by the header menus, the side rail and the footer.
export const NAV = [
  { to: '/', label: 'Overview Dashboard', group: 'Explore', icon: 'home', end: true },
  { to: '/dataset', label: 'Dataset Explorer', group: 'Explore', icon: 'database' },
  { to: '/quality', label: 'Data Quality', group: 'Data', icon: 'shield' },
  { to: '/processing', label: 'Data Processing Studio', group: 'Data', icon: 'layers' },
  { to: '/clustering', label: 'Clustering Lab', group: 'Machine learning', icon: 'cluster' },
  { to: '/clusters', label: 'Cluster Intelligence', group: 'Machine learning', icon: 'flask' },
  { to: '/anomalies', label: 'Anomaly Detection', group: 'Machine learning', icon: 'alert' },
  { to: '/geography', label: 'Geographic Intelligence', group: 'Analysis', icon: 'map' },
  { to: '/temporal', label: 'Temporal Analysis', group: 'Analysis', icon: 'clock' },
  { to: '/similar', label: 'Similar Event Search', group: 'Analysis', icon: 'search' },
  { to: '/multi-hazard', label: 'Multi-Hazard Analysis', group: 'Analysis', icon: 'bolt' },
  { to: '/impact', label: 'Impact Intelligence', group: 'Analysis', icon: 'chart' },
  { to: '/alerts', label: 'Live Alerts', group: 'Operations', icon: 'alert' },
  { to: '/routes', label: 'Route Assistance', group: 'Operations', icon: 'route' },
  { to: '/incidents', label: 'Incident Reporting', group: 'Operations', icon: 'flag' },
  { to: '/resources', label: 'Resource Management', group: 'Operations', icon: 'box' },
  { to: '/coordination', label: 'Response Coordination', group: 'Operations', icon: 'users' },
  { to: '/assistant', label: 'AI Weather Assistant', group: 'Assistant', icon: 'chat' },
  { to: '/reports', label: 'Reports', group: 'Assistant', icon: 'file' },
  { to: '/settings', label: 'Settings & Administration', group: 'Account', icon: 'sliders' },
]

export const GROUPS = [...new Set(NAV.map((n) => n.group))]

// The compact icon rail on the left shows the most-used pages.
export const RAIL = ['/', '/clustering', '/geography', '/anomalies', '/alerts', '/assistant', '/reports']
