import { useCallback, useState } from 'react';
import { Check, Copy, TriangleAlert } from 'lucide-react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button, Input, Modal } from '@/components';
import { formatDate, truncateAddress } from '@/utils/format';
import type { AdminDepositAddressRow, AdminNetworkRow } from '@/types/admin';

/** Page-level safety notice (§5) — shown above the list and inside the form. */
const ADDRESS_WARNING =
  'Only enter a real USDT receiving address that you control. Make sure it matches the selected network.';

interface AddressForm {
  network: string;
  address: string;
}

const EMPTY_FORM: AddressForm = { network: '', address: '' };

/**
 * Receiving-address manager for the deposit page (Section 6). Reads and
 * writes the EXISTING /api/admin-panel/deposit-addresses/ API — the backend
 * deactivates the previous active address for a network when a new one is
 * added, so exactly one address is live per network at all times.
 */
export function AdminDepositAddressesPage() {
  const fetcher = useCallback(async () => {
    const [addresses, networks] = await Promise.all([
      adminService.depositAddresses(),
      adminService.networks(),
    ]);
    if (!addresses.success) throw new Error(addresses.message || 'Unable to load deposit addresses.');
    return {
      addresses: addresses.data ?? [],
      networks: networks.success ? (networks.data ?? []) : [],
    };
  }, []);
  const query = useDashboardData(fetcher);
  const addresses = query.data?.addresses ?? [];
  const networks = query.data?.networks ?? [];

  const [editing, setEditing] = useState<{ mode: 'create' | 'edit'; row: AdminDepositAddressRow | null } | null>(null);
  const [form, setForm] = useState<AddressForm>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

  const selectableNetworks = networks.filter((n) => n.is_active);

  const openCreate = () => {
    setFormError(null);
    setForm({ ...EMPTY_FORM, network: selectableNetworks[0]?.code ?? '' });
    setEditing({ mode: 'create', row: null });
  };

  const openEdit = (row: AdminDepositAddressRow) => {
    setFormError(null);
    setForm({ network: row.network, address: row.address });
    setEditing({ mode: 'edit', row });
  };

  const save = async () => {
    if (!editing || busy) return;
    setBusy(true);
    setFormError(null);
    try {
      const envelope = editing.mode === 'create'
        ? await adminService.createDepositAddress(form.network.trim(), form.address.trim())
        : await adminService.updateDepositAddress(editing.row!.id, { address: form.address.trim() });
      if (!envelope.success) {
        setFormError(envelope.message || 'Save failed.');
        return;
      }
      setEditing(null);
      setNotice(envelope.message || 'Address saved.');
      query.retry();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setBusy(false);
    }
  };

  const setActive = async (row: AdminDepositAddressRow, isActive: boolean) => {
    setNotice(null);
    setFormError(null);
    try {
      const envelope = await adminService.updateDepositAddress(row.id, { is_active: isActive });
      if (!envelope.success) setFormError(envelope.message || 'Update failed.');
      else setNotice(envelope.message || 'Address updated.');
      query.retry();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Update failed.');
    }
  };

  const copyAddress = async (row: AdminDepositAddressRow) => {
    try {
      await navigator.clipboard.writeText(row.address);
      setCopied(row.id);
      window.setTimeout(() => setCopied((current) => (current === row.id ? null : current)), 1500);
    } catch {
      setFormError('Unable to copy the address to the clipboard.');
    }
  };

  /** Network that currently has another active address (rotation preview). */
  const activeNetworks = new Set(
    addresses.filter((row) => row.is_active).map((row) => row.network),
  );
  const rotationTarget =
    editing?.mode === 'create' && form.network && activeNetworks.has(form.network);

  const columns = [
    {
      key: 'network',
      header: 'Network',
      render: (row: AdminDepositAddressRow) => (
        <div>
          <span className="font-semibold text-white">{row.network}</span>
          <span className="block text-xs text-surface-500">{row.network_name}</span>
        </div>
      ),
    },
    { key: 'asset', header: 'Asset', render: (row: AdminDepositAddressRow) => row.asset },
    {
      key: 'address',
      header: 'Address',
      className: 'max-w-[16rem]',
      render: (row: AdminDepositAddressRow) => (
        <div className="flex items-center gap-1.5">
          <code className="truncate font-mono text-xs text-surface-300" title={row.address}>
            {truncateAddress(row.address, 10, 8)}
          </code>
          <button
            type="button"
            onClick={() => void copyAddress(row)}
            className="rounded-lg p-1.5 text-surface-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="Copy full address"
          >
            {copied === row.id ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: AdminDepositAddressRow) => (
        <AdminStatusBadge status={row.is_active ? 'ACTIVE' : 'CLOSED'} />
      ),
    },
    { key: 'created', header: 'Created', render: (row: AdminDepositAddressRow) => formatDate(row.created_at) },
    {
      key: 'actions',
      header: 'Actions',
      render: (row: AdminDepositAddressRow) => (
        <div className="flex gap-1.5">
          <Button size="sm" variant="secondary" onClick={() => openEdit(row)}>Edit</Button>
          {row.is_active ? (
            <Button size="sm" variant="ghost" onClick={() => void setActive(row, false)}>Deactivate</Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => void setActive(row, true)}>Activate</Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <AdminPageHeader
        title="Deposit Addresses"
        subtitle="Receiving addresses shown on the user deposit page. One active address per network."
        actions={<Button onClick={openCreate} disabled={selectableNetworks.length === 0}>New address</Button>}
      />

      <div className="mb-4 flex gap-2.5 rounded-2xl border border-amber-500/30 bg-amber-500/5 px-4 py-3">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden />
        <p className="text-xs leading-relaxed text-amber-200">{ADDRESS_WARNING}</p>
      </div>

      {notice && <p className="mb-3 rounded-xl bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">{notice}</p>}
      {formError && !editing && <p className="mb-3 rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{formError}</p>}

      <AdminTable<AdminDepositAddressRow>
        columns={columns}
        rows={addresses.length > 0 ? addresses : null}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage={
          selectableNetworks.length === 0
            ? 'No networks configured yet'
            : 'No deposit addresses yet — add one to make the deposit page usable'
        }
        rowKey={(row) => String(row.id)}
        page={1}
        pageCount={1}
        onPageChange={() => undefined}
        count={addresses.length}
      />

      <Modal
        open={editing !== null}
        onClose={() => { if (!busy) setEditing(null); }}
        title={editing?.mode === 'create' ? 'Add deposit address' : `Edit address: ${editing?.row?.network ?? ''}/USDT`}
        description="Adding a new address for a network automatically deactivates its previous active address."
      >
        <div className="space-y-3">
          {editing?.mode === 'create' ? (
            <div className="flex w-full flex-col gap-1.5">
              <label htmlFor="deposit-address-network" className="text-sm font-medium text-surface-900">
                Network
              </label>
              <select
                id="deposit-address-network"
                value={form.network}
                onChange={(e) => setForm((f) => ({ ...f, network: e.target.value }))}
                className="h-11 w-full rounded-xl border border-surface-200 bg-white px-3.5 text-sm text-surface-900 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
              >
                {selectableNetworks.length === 0 && <option value="">No networks available</option>}
                {selectableNetworks.map((network: AdminNetworkRow) => (
                  <option key={network.code} value={network.code}>
                    {network.code} — {network.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="rounded-xl bg-surface-50 px-3.5 py-2.5 text-sm text-surface-700">
              Network: <span className="font-semibold text-surface-900">{editing?.row?.network}</span> ({editing?.row?.network_name})
            </div>
          )}

          <Input
            label="USDT receiving address"
            value={form.address}
            maxLength={255}
            inputMode="text"
            spellCheck={false}
            autoComplete="off"
            placeholder="Paste the real on-chain address"
            hint="Stored exactly as entered — shown to users with a QR code on the deposit page."
            onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
          />

          <div className="rounded-xl bg-surface-50 px-3.5 py-2.5 text-sm text-surface-700">
            Asset: <span className="font-semibold text-surface-900">USDT</span>
          </div>

          {rotationTarget && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              This network already has an active address. Saving will deactivate it and make the new address live.
            </p>
          )}

          <div className="flex gap-2.5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
            <p className="text-xs leading-relaxed text-amber-800">{ADDRESS_WARNING}</p>
          </div>

          {formError && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{formError}</p>}
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={() => setEditing(null)} disabled={busy}>Cancel</Button>
            <Button
              fullWidth
              isLoading={busy}
              onClick={() => void save()}
              disabled={editing?.mode === 'create' && (!form.network || !form.address.trim())}
            >
              {editing?.mode === 'create' ? 'Add address' : 'Save address'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
