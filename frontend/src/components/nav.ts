import {
  Boxes, Camera, Database, FileBarChart, History, LayoutDashboard, ScanFace, ScanLine, Settings, ShieldCheck, Upload, type LucideIcon,
} from 'lucide-react'
import type { Role } from '@/types/auth'

export interface NavItem { to: string; label: string; icon: LucideIcon; roles?: Role[] }
export interface NavGroup { label: string; items: NavItem[] }

const VERIFIERS: Role[] = ['administrator', 'researcher', 'operator'] // viewers are read-only
const MANAGERS: Role[] = ['administrator', 'researcher']

export const navGroups: NavGroup[] = [
  { label: 'Monitor', items: [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/reports', label: 'Reports', icon: FileBarChart },
  ] },
  { label: 'Verify', items: [
    { to: '/camera', label: 'Record with camera', icon: Camera },
    { to: '/verify', label: 'Live verification', icon: ScanFace, roles: VERIFIERS },
    { to: '/challenge', label: 'Liveness challenge', icon: ScanLine, roles: VERIFIERS },
    { to: '/uploads', label: 'Upload', icon: Upload, roles: VERIFIERS },
    { to: '/history', label: 'History', icon: History },
  ] },
  { label: 'AI workspace', items: [
    { to: '/models', label: 'Models', icon: Boxes },
    { to: '/datasets', label: 'Datasets', icon: Database, roles: MANAGERS },
  ] },
  { label: 'Account', items: [
    { to: '/settings', label: 'Profile & settings', icon: Settings },
    { to: '/admin', label: 'Administration', icon: ShieldCheck, roles: ['administrator'] },
  ] },
]

/** Navigation filtered by role. Hiding is a convenience only: the API enforces permissions on its own. */
export function visibleGroups(role: Role | undefined): NavGroup[] {
  return navGroups
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.roles || (role !== undefined && i.roles.includes(role))) }))
    .filter((g) => g.items.length > 0)
}
