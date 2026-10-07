import type { SVGProps } from 'react'

const base = { width: 24, height: 24, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' } as const
type P = SVGProps<SVGSVGElement>

export const IconMonitor = (p: P) => (<svg {...base} {...p} aria-hidden="true"><rect x="3" y="6" width="13" height="10" rx="1.5" /><path d="M16 9.5 21 7v10l-5-2.5" /><path d="M7 20h6" /></svg>)
export const IconPlan = (p: P) => (<svg {...base} {...p} aria-hidden="true"><rect x="3" y="3" width="18" height="18" /><path d="M3 9h18M9 3v18M15 9v12" /><circle cx="18" cy="6" r="1.2" /></svg>)
export const IconZones = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M4 7 11 4l9 5-2 10-11 1Z" /><path d="m7 15 4-4M9 18l6-6M12 19l5-5" /></svg>)
export const IconCalibrate = (p: P) => (<svg {...base} {...p} aria-hidden="true"><circle cx="12" cy="12" r="7" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /><circle cx="12" cy="12" r="1.5" /></svg>)
export const IconLog = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M8 6h12M8 12h12M8 18h12" /><circle cx="4" cy="6" r="1" /><circle cx="4" cy="12" r="1" /><circle cx="4" cy="18" r="1" /></svg>)
export const IconRisk = (p: P) => (<svg {...base} {...p} aria-hidden="true"><rect x="3" y="3" width="5" height="5" /><rect x="10" y="3" width="5" height="5" /><rect x="17" y="3" width="4" height="5" /><rect x="3" y="10" width="5" height="5" /><rect x="10" y="10" width="5" height="5" fill="currentColor" /><rect x="17" y="10" width="4" height="5" /><path d="M3 19h18" /></svg>)
export const IconReport = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M6 3h9l4 4v14H6z" /><path d="M15 3v4h4M9 12h7M9 16h7M9 8h3" /></svg>)
export const IconSettings = (p: P) => (<svg {...base} {...p} aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" /></svg>)
export const IconSpeaker = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M17 9a4 4 0 0 1 0 6M19.5 6.5a8 8 0 0 1 0 11" /></svg>)
export const IconMute = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" /><path d="m17 9 5 6M22 9l-5 6" /></svg>)
export const IconExpand = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M4 9V4h5M20 15v5h-5M4 4l6 6M20 20l-6-6" /></svg>)
export const IconCheck = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="m5 12 4 4 10-10" /></svg>)
export const IconPlus = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>)
export const IconTrash = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>)
export const IconPrint = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M7 9V3h10v6M7 17H4v-7h16v7h-3" /><rect x="7" y="14" width="10" height="7" /></svg>)
export const IconPlay = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>)
export const IconUpload = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></svg>)
export const IconDownload = (p: P) => (<svg {...base} {...p} aria-hidden="true"><path d="M12 4v12M7 11l5 5 5-5M4 20h16" /></svg>)
