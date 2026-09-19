import { useCallback, useMemo, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader } from '@/components/admin';
import { Button, Modal } from '@/components';
import type { AdminSetting } from '@/types/admin';

type Group = 'all' | 'general' | 'deposit' | 'withdrawal' | 'vip' | 'referral' | 'reward' | 'security' | 'maintenance';

const GROUPS: Array<{ key: Group; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'general', label: 'General' },
  { key: 'deposit', label: 'Deposit' },
  { key: 'withdrawal', label: 'Withdrawal' },
  { key: 'vip', label: 'VIP' },
  { key: 'referral', label: 'Referral' },
  { key: 'reward', label: 'Reward' },
  { key: 'security', label: 'Security' },
  { key: 'maintenance', label: 'Maintenance' },
];

/** Platform settings (§56–63): grouped, every edit audited server-side. */
export function AdminSettingsPage() {
  const [group, setGroup] = useState<Group>('all');
  const [editing, setEditing] = useState<AdminSetting | null>(null);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const fetcher = useCallback(async () => {
    const response = await adminService.settings();
    if (!response.success) throw new Error(response.message || 'Unable to load settings.');
    return response;
  }, []);
  const query = useDashboardData(fetcher);
  const settings = useMemo(() => {
    const all = query.data?.data?.results ?? [];
    return group === 'all' ? all : all.filter((s) => (s as AdminSetting & { group?: string }).group === group);
  }, [query.data, group]);

  const openEdit = (setting: AdminSetting) => {
    setError(null);
    setValue(setting.value);
    setEditing(setting);
  };

  const save = async () => {
    if (!editing || busy) return;
    setBusy(true);
    setError(null);
    try {
      const envelope = await adminService.updateSetting(editing.key, value.trim());
      if (!envelope.success) {
        setError(envelope.message || 'Update failed.');
        return;
      }
      setNotice(`Setting "${editing.key}" updated — change recorded in the audit log.`);
      setEditing(null);
      query.retry();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Update failed.');
    } finally {
      setBusy(false);
    }
  };

  const renderValue = (setting: AdminSetting) => {
    if (setting.value_type === 'boolean') {
      const on = setting.value.toLowerCase() === 'true';
      return (
        <span className={on ? 'text-xs font-semibold text-emerald-300' : 'text-xs font-semibold text-surface-400'}>
          {on ? 'ON' : 'OFF'}
        </span>
      );
    }
    return <span className="max-w-[14rem] truncate font-mono text-xs text-surface-200">{setting.value || '—'}</span>;
  };

  return (
    <div>
      <AdminPageHeader title="Settings" subtitle="Platform configuration. Every modification is audited with actor, key, and values." />

      <div className="mb-3">
        <AdminFilterChips options={GROUPS} value={group} onChange={setGroup} />
      </div>

      {notice && <p className="mb-3 rounded-xl bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">{notice}</p>}

      {query.isLoading ? (
        <div className="space-y-2">{[0, 1, 2, 3].map((i) => <div key={i} className="h-12 animate-pulse rounded-xl bg-white/5" />)}</div>
      ) : query.error ? (
        <div className="rounded-2xl border border-white/10 bg-surface-900 p-6 text-center text-sm text-surface-300">{query.error}</div>
      ) : settings.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-surface-400">No settings in this group</div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-[11px] uppercase tracking-wide text-surface-400">
              <tr>
                <th scope="col" className="px-4 py-3 font-semibold">Key</th>
                <th scope="col" className="px-4 py-3 font-semibold">Value</th>
                <th scope="col" className="hidden px-4 py-3 font-semibold md:table-cell">Description</th>
                <th scope="col" className="px-4 py-3 text-right font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {settings.map((setting) => (
                <tr key={setting.key} className="text-surface-200 transition-colors hover:bg-white/5">
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-surface-100">{setting.key}</span>
                    <span className="ml-2 rounded bg-white/5 px-1.5 py-0.5 text-[10px] uppercase text-surface-500">{setting.value_type}</span>
                  </td>
                  <td className="px-4 py-3">{renderValue(setting)}</td>
                  <td className="hidden max-w-[20rem] px-4 py-3 text-xs text-surface-400 md:table-cell">{setting.description || '—'}</td>
                  <td className="px-4 py-3 text-right">
                    <Button size="sm" variant="secondary" onClick={() => openEdit(setting)}>Edit</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit modal */}
      <Modal open={editing !== null} onClose={() => { if (!busy) setEditing(null); }} title={`Edit setting: ${editing?.key ?? ''}`} description="The change is audited; secrets are never displayed or logged.">
        {editing && (
          <div className="space-y-3">
            {editing.value_type === 'boolean' ? (
              <label className="flex items-center gap-2 text-sm text-surface-200">
                <input
                  type="checkbox"
                  checked={value.toLowerCase() === 'true'}
                  onChange={(e) => setValue(String(e.target.checked))}
                  className="h-4 w-4 rounded border-white/20 bg-surface-900"
                />
                Enabled
              </label>
            ) : (
              <div>
                <label htmlFor="setting-value" className="mb-1 block text-xs font-medium text-surface-400">New value ({editing.value_type})</label>
                <input
                  id="setting-value"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-surface-950 px-3 py-2.5 font-mono text-xs text-surface-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            )}
            <p className="text-xs text-surface-500">Current value: <span className="font-mono">{editing.value || '(empty)'}</span></p>
            {error && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</p>}
            <div className="flex gap-2">
              <Button variant="secondary" fullWidth onClick={() => setEditing(null)} disabled={busy}>Cancel</Button>
              <Button fullWidth isLoading={busy} onClick={() => void save()}>Save setting</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
