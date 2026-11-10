import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, ScrollText, Search, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/PageHeader'
import { ResetLinkDialog } from '@/components/ResetLinkDialog'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Pagination } from '@/components/ui/pagination'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, ErrorState } from '@/components/ui/state'
import { useAuth } from '@/hooks/useAuth'
import { errorMessage } from '@/services/api'
import { listAudit } from '@/services/history'
import { listUsers, updateUser } from '@/services/users'
import type { AuthUser, Role } from '@/types/auth'
import { cn } from '@/utils/cn'
import { formatDateTime } from '@/utils/format'
import { useT } from '@/i18n'
import { roleLabel } from '@/i18n/labels'

const ROLES: Role[] = ['administrator', 'researcher', 'operator', 'viewer']
const ROLE_HELP: Record<Role, string> = {
  administrator: 'Manages users, models and datasets', researcher: 'Datasets and models', operator: 'Runs verifications', viewer: 'Read-only',
}

function UsersTab() {
  const { t } = useT()
  const { user: me } = useAuth()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [toggle, setToggle] = useState<AuthUser | null>(null)
  const [resetFor, setResetFor] = useState<AuthUser | null>(null)
  const users = useQuery({ queryKey: ['admin-users'], queryFn: () => listUsers(), retry: false })
  const mut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { role?: Role; is_active?: boolean } }) => updateUser(id, patch),
    onSuccess: () => { toast.success(t('User updated.')); setToggle(null); void qc.invalidateQueries({ queryKey: ['admin-users'] }) },
    onError: (e) => { toast.error(errorMessage(e)); setToggle(null) },
  })
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (users.data?.items ?? []).filter((u) => !q || u.email.toLowerCase().includes(q) || u.full_name.toLowerCase().includes(q))
  }, [users.data, search])

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm"><Search className="absolute left-2.5 top-2.5 size-4 text-muted" />
        <input aria-label={t('Search users')} value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('Search name or email…')} className="h-9 w-full rounded-lg border border-border bg-bg pl-8 pr-2 text-sm" /></div>
      {users.isError && <ErrorState title={t('Users unavailable')} message={errorMessage(users.error)} onRetry={() => void users.refetch()} />}
      <Card className="overflow-hidden">
        {users.isLoading ? <div className="space-y-3 p-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-5" />)}</div>
          : rows.length === 0 ? <EmptyState icon={Users} title={t('No users match')} />
          : <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-border text-xs text-muted"><tr><th scope="col" className="px-4 py-2.5 font-medium">{t('User')}</th><th scope="col" className="px-4 py-2.5 font-medium">{t('Role')}</th><th scope="col" className="px-4 py-2.5 font-medium">{t('Status')}</th><th scope="col" className="px-4 py-2.5 font-medium">{t('Last sign-in')}</th><th scope="col" className="px-4 py-2.5 text-right font-medium">{t('Password')}</th></tr></thead>
            <tbody className="divide-y divide-border">{rows.map((u) => {
              const self = u.id === me?.id
              return (
                <tr key={u.id}>
                  <td className="px-4 py-3"><p className="font-medium">{u.full_name}{self && <span className="ml-2 text-xs text-muted">{t('(you)')}</span>}</p><p className="text-xs text-muted">{u.email}</p></td>
                  <td className="px-4 py-3">
                    <select aria-label={t('Role for {email}', { email: u.email })} value={u.role} disabled={self || mut.isPending} title={self ? t('You cannot change your own role') : t(ROLE_HELP[u.role])}
                      onChange={(e) => mut.mutate({ id: u.id, patch: { role: e.target.value as Role } })} className="h-8 rounded-lg border border-border bg-bg px-2 text-sm capitalize disabled:opacity-60">
                      {ROLES.map((r) => <option key={r} value={r}>{roleLabel(r)}</option>)}</select></td>
                  <td className="px-4 py-3"><Button variant="outline" size="sm" disabled={self || mut.isPending} title={self ? t('You cannot disable yourself') : undefined} onClick={() => u.is_active ? setToggle(u) : mut.mutate({ id: u.id, patch: { is_active: true } })}>
                    <span className={cn('size-2 rounded-full', u.is_active ? 'bg-success' : 'bg-danger')} />{u.is_active ? t('Active: disable') : t('Disabled: enable')}</Button></td>
                  <td className="px-4 py-3 text-muted">{u.last_login_at ? formatDateTime(u.last_login_at) : '—'}</td>
                  <td className="px-4 py-3 text-right">{!self && <Button variant="ghost" size="sm" disabled={!u.is_active} title={u.is_active ? t('Create a one-time password reset link') : t('Enable the account first')}
                    aria-label={t('Reset link for {email}', { email: u.email })} onClick={() => setResetFor(u)}><KeyRound className="size-4" />{t('Reset link')}</Button>}</td>
                </tr>)
            })}</tbody></table></div>}
      </Card>
      <p className="text-xs text-muted">{t('Role changes take effect immediately. Disabling an account ends its sessions. Administrators cannot change their own role or status. A reset link lets a user who forgot their password choose a new one without e-mail.')}</p>
      <ResetLinkDialog user={resetFor} onClose={() => setResetFor(null)} />
      <ConfirmDialog open={!!toggle} onOpenChange={(o) => !o && setToggle(null)} title={t('Disable {name}?', { name: toggle?.full_name ?? t('this user') })} confirmLabel={t('Disable')}
        description={t('They will be signed out and unable to sign in until an administrator enables the account again.')} busy={mut.isPending}
        onConfirm={() => toggle && mut.mutate({ id: toggle.id, patch: { is_active: false } })} />
    </div>
  )
}

const KNOWN_ACTIONS = ['auth.register', 'auth.login', 'auth.login_failed', 'auth.logout', 'auth.refresh_replay', 'auth.password_change', 'user.update',
  'verification.run', 'verification.delete', 'verification.export', 'verification.access_denied', 'upload.rejected', 'dataset.create', 'dataset.delete',
  'dataset.export', 'model.register', 'model.activate', 'model.activate_refused', 'model.deactivate', 'model.delete', 'user.reset_link_created', 'report.export']

function AuditTab() {
  const { t } = useT()
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const audit = useQuery({ queryKey: ['audit', page, action], queryFn: () => listAudit(page, action), placeholderData: keepPreviousData, retry: false })
  return (
    <div className="space-y-4">
      <div className="max-w-xs"><label htmlFor="audit-action" className="mb-1 block text-xs text-muted">{t('Event type')}</label>
        <input id="audit-action" list="audit-actions" value={action} onChange={(e) => { setAction(e.target.value.trim()); setPage(1) }} placeholder={t('All events')} className="h-9 w-full rounded-lg border border-border bg-bg px-2.5 text-sm" />
        <datalist id="audit-actions">{KNOWN_ACTIONS.map((a) => <option key={a} value={a} />)}</datalist></div>
      {audit.isError && <ErrorState title={t('Audit log unavailable')} message={errorMessage(audit.error)} onRetry={() => void audit.refetch()} />}
      <Card className="overflow-hidden">
        {audit.isLoading ? <div className="space-y-3 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-5" />)}</div>
          : audit.data && audit.data.items.length > 0 ? <>
            <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-border text-xs text-muted"><tr>{['Time', 'Event', 'User', 'IP', 'Details'].map((h) => <th key={h} scope="col" className="px-4 py-2.5 font-medium">{t(h)}</th>)}</tr></thead>
              <tbody className="divide-y divide-border">{audit.data.items.map((a) => (
                <tr key={a.id}><td className="whitespace-nowrap px-4 py-3 text-muted">{formatDateTime(a.created_at)}</td><td className="px-4 py-3 font-mono text-xs">{a.action}</td>
                  <td className="px-4 py-3">{a.user_email ?? '—'}</td><td className="px-4 py-3 text-muted">{a.ip_address ?? '—'}</td>
                  <td className="max-w-xs truncate px-4 py-3 font-mono text-xs text-muted" title={a.details ? JSON.stringify(a.details) : undefined}>{a.details ? JSON.stringify(a.details) : '—'}</td></tr>))}</tbody></table></div>
            <Pagination page={audit.data.page} pageSize={audit.data.page_size} total={audit.data.total} onPage={setPage} /></>
          : <EmptyState icon={ScrollText} title={t('No events')} hint={action ? t('No events of that type.') : t('Security events appear here.')} />}
      </Card>
    </div>
  )
}

export default function AdminPage() {
  const { t } = useT()
  const [tab, setTab] = useState<'users' | 'audit'>('users')
  return (
    <div className="space-y-6">
      <PageHeader title={t('Administration')} description={t('Manage accounts and review security events.')} />
      <div role="tablist" aria-label={t('Administration')} className="flex gap-1 border-b border-border">
        {([['users', 'Users'], ['audit', 'Audit log']] as const).map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cn('-mb-px cursor-pointer border-b-2 px-4 py-2 text-sm', tab === k ? 'border-primary text-fg' : 'border-transparent text-muted hover:text-fg')}>{t(label)}</button>))}
      </div>
      <div role="tabpanel">{tab === 'users' ? <UsersTab /> : <AuditTab />}</div>
    </div>
  )
}
