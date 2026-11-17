import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Eye, ScrollText } from "lucide-react";
import api from "../../api/client";
import { formatDateTime, titleize } from "../../lib/format";
import { Alert, Badge, Button, Input, Modal, PageHeader, Select } from "../../components/ui";
import { DataTable } from "../../components/DataTable";

const ENTITY_TYPES = ["", "user", "organization", "vehicle", "quotation_request", "quotation", "application", "policy", "payment", "refund", "claim", "inspection", "product", "commission"];

export default function AuditLog() {
  const [entity, setEntity] = useState("");
  const [actor, setActor] = useState("");
  const [selected, setSelected] = useState(null);

  const logs = useQuery({
    queryKey: ["audit-logs", { entity, actor }],
    queryFn: async () => (await api.get(`/admin/audit-logs/?limit=200${entity ? `&entity_type=${entity}` : ""}${actor ? `&actor=${encodeURIComponent(actor)}` : ""}`)).data,
  });

  const rows = Array.isArray(logs.data) ? logs.data : [];

  return (
    <div>
      <PageHeader
        eyebrow="Governance"
        title="Audit log"
        description="Immutable trail of consequential actions across the platform."
        actions={<Button variant="secondary" onClick={() => logs.refetch()} loading={logs.isFetching}>Refresh</Button>}
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:w-2/3">
        <Select label="Entity type" value={entity} onChange={(event) => setEntity(event.target.value)} options={ENTITY_TYPES.map((value) => ({ value, label: value ? titleize(value) : "All entities" }))} />
        <Input label="Actor email" value={actor} onChange={(event) => setActor(event.target.value)} placeholder="Filter by email" />
      </div>

      <DataTable
        loading={logs.isLoading}
        error={logs.isError}
        onRetry={logs.refetch}
        rows={rows}
        columns={[
          { header: "When", cell: (row) => <span className="text-xs text-ink-500">{formatDateTime(row.created_at)}</span> },
          { header: "Actor", cell: (row) => <span className="text-xs font-semibold text-ink-800">{row.actor || "System"}</span> },
          { header: "Action", cell: (row) => <Badge tone="brand">{row.action}</Badge> },
          { header: "Entity", cell: (row) => <div><p className="text-xs text-ink-700">{titleize(row.entity_type)}</p><p className="mt-0.5 font-mono text-[10px] text-ink-400">{row.entity_id ? String(row.entity_id).slice(0, 8) : "—"}</p></div> },
          { header: "IP", cell: (row) => <span className="font-mono text-[10px] text-ink-500">{row.ip_address || "—"}</span> },
          { header: "", className: "text-right", cell: (row) => <Button size="sm" variant="ghost" icon={Eye} onClick={() => setSelected(row)}>Details</Button> },
        ]}
        empty={<div className="surface p-10 text-center"><ScrollText className="mx-auto h-8 w-8 text-ink-300" /><p className="mt-3 text-sm font-bold text-ink-800">No audit entries</p><p className="mt-1 text-xs text-ink-400">Actions will appear here as they happen.</p></div>}
      />

      <Modal open={Boolean(selected)} onClose={() => setSelected(null)} title="Audit entry" description={selected?.action} wide footer={<Button variant="secondary" onClick={() => setSelected(null)}>Close</Button>}>
        {selected && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl bg-ink-50 p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Actor</p><p className="mt-1 text-sm font-semibold text-ink-900">{selected.actor || "System"}</p></div>
              <div className="rounded-xl bg-ink-50 p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">When</p><p className="mt-1 text-sm font-semibold text-ink-900">{formatDateTime(selected.created_at)}</p></div>
              <div className="rounded-xl bg-ink-50 p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">Entity</p><p className="mt-1 text-sm font-semibold text-ink-900">{titleize(selected.entity_type)}</p><p className="mt-1 break-all font-mono text-[10px] text-ink-500">{selected.entity_id}</p></div>
              <div className="rounded-xl bg-ink-50 p-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-ink-400">IP address</p><p className="mt-1 font-mono text-sm text-ink-900">{selected.ip_address || "—"}</p></div>
            </div>
            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-500">Changes</p>
              <pre className="max-h-80 overflow-auto rounded-xl bg-ink-950 p-4 text-[11px] leading-relaxed text-lime-200">{selected.changes ? JSON.stringify(selected.changes, null, 2) : "No change payload recorded."}</pre>
            </div>
            <Alert tone="info">Audit records are append-only. If you suspect unauthorised activity, escalate to security.</Alert>
          </div>
        )}
      </Modal>
    </div>
  );
}
