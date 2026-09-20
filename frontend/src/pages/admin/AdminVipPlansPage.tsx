import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button, Input, Modal } from '@/components';
import { formatUsdt } from '@/utils/format';
import type { AdminVipPlan } from '@/types/admin';

interface PlanForm {
  name: string;
  plan_number: string;
  investment_amount: string;
  target_amount: string;
  daily_rate: string;
  sort_order: string;
  is_active: boolean;
}

const EMPTY_FORM: PlanForm = {
  name: '',
  plan_number: '',
  investment_amount: '',
  target_amount: '',
  daily_rate: '',
  sort_order: '0',
  is_active: true,
};

/**
 * VIP plan management (§30–33): CRUD on plans while every historical
 * purchase keeps its snapshot terms (the backend never rewrites purchases).
 * All financial fields are Decimals validated server-side (§31–32).
 */
export function AdminVipPlansPage() {
  const fetcher = useCallback(async () => {
    const response = await adminService.vipPlans();
    if (!response.success) throw new Error(response.message || 'Unable to load plans.');
    return response;
  }, []);
  const query = useDashboardData(fetcher);
  const plans = query.data?.data?.results ?? [];

  const [editing, setEditing] = useState<{ mode: 'create' | 'edit'; plan: AdminVipPlan | null } | null>(null);
  const [form, setForm] = useState<PlanForm>(EMPTY_FORM);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const openCreate = () => {
    setFormError(null);
    setForm(EMPTY_FORM);
    setEditing({ mode: 'create', plan: null });
  };

  const openEdit = (plan: AdminVipPlan) => {
    setFormError(null);
    setForm({
      name: plan.name,
      plan_number: String(plan.plan_number),
      investment_amount: plan.investment_amount,
      target_amount: plan.target_amount,
      daily_rate: plan.daily_rate,
      sort_order: String(plan.sort_order),
      is_active: plan.is_active,
    });
    setEditing({ mode: 'edit', plan });
  };

  const save = async () => {
    if (!editing || busy) return;
    setBusy(true);
    setFormError(null);
    try {
      const payload = {
        name: form.name.trim(),
        plan_number: form.plan_number.trim(),
        investment_amount: form.investment_amount.trim(),
        target_amount: form.target_amount.trim(),
        daily_rate: form.daily_rate.trim(),
        sort_order: form.sort_order.trim(),
        is_active: form.is_active,
      };
      const envelope = editing.mode === 'create'
        ? await adminService.createVipPlan(payload)
        : await adminService.updateVipPlan(editing.plan!.id, payload);
      if (!envelope.success) {
        setFormError(envelope.message || 'Save failed.');
        return;
      }
      setEditing(null);
      setNotice('Plan saved. Existing purchases keep their snapshot terms.');
      query.retry();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (plan: AdminVipPlan) => {
    setFormError(null);
    try {
      const envelope = await adminService.updateVipPlan(plan.id, { is_active: !plan.is_active });
      if (!envelope.success) setFormError(envelope.message || 'Update failed.');
      else query.retry();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Update failed.');
    }
  };

  const columns = [
    { key: 'plan', header: 'Plan', render: (row: AdminVipPlan) => <span className="font-semibold text-white">{row.name}</span> },
    { key: 'inv', header: 'Investment', render: (row: AdminVipPlan) => <span className="tabular-nums">{formatUsdt(row.investment_amount)}</span> },
    { key: 'target', header: 'Target', render: (row: AdminVipPlan) => <span className="tabular-nums">{formatUsdt(row.target_amount)}</span> },
    { key: 'rate', header: 'Daily rate', render: (row: AdminVipPlan) => <span className="tabular-nums">{row.daily_rate}%</span> },
    { key: 'active', header: 'Status', render: (row: AdminVipPlan) => (
      <AdminStatusBadge status={row.is_active ? 'ACTIVE' : 'CLOSED'} />
    ) },
    {
      key: 'actions',
      header: 'Actions',
      render: (row: AdminVipPlan) => (
        <div className="flex gap-1.5">
          <Button size="sm" variant="secondary" onClick={() => openEdit(row)}>Edit</Button>
          <Button size="sm" variant="ghost" onClick={() => void toggleActive(row)}>
            {row.is_active ? 'Deactivate' : 'Activate'}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <AdminPageHeader
        title="VIP Plans"
        subtitle="Plan configuration. Historical purchases always retain their snapshot terms."
        actions={<Button onClick={openCreate}>New plan</Button>}
      />

      {notice && <p className="mb-3 rounded-xl bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">{notice}</p>}
      {formError && !editing && <p className="mb-3 rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{formError}</p>}

      <AdminTable<AdminVipPlan>
        columns={columns}
        rows={plans.length > 0 ? plans : null}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No VIP plans configured"
        rowKey={(row) => String(row.id)}
        page={1}
        pageCount={1}
        onPageChange={() => undefined}
        count={plans.length}
      />

      <Modal
        open={editing !== null}
        onClose={() => { if (!busy) setEditing(null); }}
        title={editing?.mode === 'create' ? 'Create VIP plan' : `Edit plan: ${editing?.plan?.name ?? ''}`}
        description="All amounts are validated server-side as Decimals."
      >
        <div className="space-y-3">
          <Input
            label="Plan name"
            value={form.name}
            maxLength={100}
            hint="Plans named WELCOME… may set investment 0 (free welcome plan)."
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Plan number"
              value={form.plan_number}
              onChange={(e) => setForm((f) => ({ ...f, plan_number: e.target.value }))}
            />
            <Input
              label="Display order"
              value={form.sort_order}
              onChange={(e) => setForm((f) => ({ ...f, sort_order: e.target.value }))}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Investment amount (USDT)"
              value={form.investment_amount}
              inputMode="decimal"
              hint="0 allowed only for a WELCOME plan."
              onChange={(e) => setForm((f) => ({ ...f, investment_amount: e.target.value }))}
            />
            <Input
              label="Target amount (USDT)"
              value={form.target_amount}
              inputMode="decimal"
              hint="For a WELCOME plan this is the one-time welcome reward."
              onChange={(e) => setForm((f) => ({ ...f, target_amount: e.target.value }))}
            />
          </div>
          <Input
            label="Daily rate (fraction)"
            value={form.daily_rate}
            inputMode="decimal"
            hint="Fraction of investment per day (0.25 = 25%). Applies only to new purchases."
            onChange={(e) => setForm((f) => ({ ...f, daily_rate: e.target.value }))}
          />
          <label className="flex items-center gap-2 text-sm text-surface-200">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="h-4 w-4 rounded border-white/20 bg-surface-900"
            />
            Active (available for purchase)
          </label>

          {formError && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{formError}</p>}
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={() => setEditing(null)} disabled={busy}>Cancel</Button>
            <Button fullWidth isLoading={busy} onClick={() => void save()}>Save plan</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
