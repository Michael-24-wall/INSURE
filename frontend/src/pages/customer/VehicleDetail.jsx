import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CalendarCheck, Car, FileText, Pencil, ShieldCheck, Upload } from "lucide-react";
import api, { getErrorMessage, listData } from "../../api/client";
import { formatCurrency, formatDate, titleize } from "../../lib/format";
import VehicleFormModal from "../../components/VehicleFormModal";
import FileDownload from "../../components/FileDownload";
import { useToast } from "../../context/ToastContext";
import { Alert, Button, Modal, PageHeader, PageLoader, SectionTitle, Select, StatusBadge, Textarea, Input } from "../../components/ui";
import { DetailItem } from "../../components/DataTable";

export default function VehicleDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editOpen, setEditOpen] = useState(false);
  const [docOpen, setDocOpen] = useState(false);
  const [inspectOpen, setInspectOpen] = useState(false);
  const [docType, setDocType] = useState("logbook");
  const [docFile, setDocFile] = useState(null);
  const [inspectionType, setInspectionType] = useState("pre_insurance");
  const [inspectionNotes, setInspectionNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const vehicle = useQuery({
    queryKey: ["vehicle", id],
    queryFn: async () => (await api.get(`/vehicles/${id}/`)).data,
  });
  const documents = useQuery({
    queryKey: ["vehicle-documents", id],
    queryFn: async () => (await api.get(`/vehicles/${id}/documents/`)).data,
  });
  const inspections = useQuery({
    queryKey: ["inspections", "vehicle", id],
    queryFn: async () => (await api.get(`/inspections/?vehicle=${id}&page_size=20`)).data,
  });

  if (vehicle.isLoading) return <PageLoader />;
  if (vehicle.isError) return <Alert>Could not load this vehicle.</Alert>;
  const v = vehicle.data;
  const docs = listData(documents.data);
  const inspectionRows = listData(inspections.data);

  async function uploadDocument(event) {
    event.preventDefault();
    if (!docFile) return;
    setSaving(true);
    setError("");
    const form = new FormData();
    form.append("document_type", docType);
    form.append("file", docFile);
    try {
      await api.post(`/vehicles/${id}/documents/`, form);
      queryClient.invalidateQueries({ queryKey: ["vehicle-documents", id] });
      toast.push("Document uploaded.", "success");
      setDocOpen(false);
      setDocFile(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function requestInspection(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const { data } = await api.post("/inspections/", {
        vehicle: id,
        inspection_type: inspectionType,
        notes: inspectionNotes,
      });
      queryClient.invalidateQueries({ queryKey: ["inspections"] });
      toast.push("Inspection requested.", "success");
      setInspectOpen(false);
      navigate(`/inspections/${data.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <Link to="/app/vehicles" className="mb-4 inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500 hover:text-ink-900"><ArrowLeft className="h-3.5 w-3.5" /> Back to vehicles</Link>
      <PageHeader
        eyebrow={`${titleize(v.category)} · ${v.manufacturing_year}`}
        title={`${v.registration_number} · ${v.make} ${v.model}`}
        description={`${titleize(v.fuel_type)} · ${titleize(v.usage)} use · ${v.color || "Colour not specified"}`}
        actions={
          <>
            <Link to={`/app/marketplace?vehicle=${v.id}`}><Button icon={ShieldCheck}>Get a quote</Button></Link>
            <Button variant="secondary" icon={Pencil} onClick={() => setEditOpen(true)}>Edit</Button>
          </>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <div>
          <div className="surface overflow-hidden">
            <div className="relative h-44 bg-gradient-to-br from-ink-950 via-ink-900 to-brand-900 p-6">
              <div className="landing-grid absolute inset-0 opacity-30" />
              <div className="relative flex h-full items-center justify-between">
                <div>
                  <p className="font-display text-4xl font-bold tracking-tight text-white">{v.registration_number}</p>
                  <p className="mt-1 text-sm text-white/50">{v.make} {v.model} · {v.manufacturing_year}</p>
                </div>
                <Car className="h-20 w-20 text-lime-300/60" />
              </div>
            </div>
            <div className="grid gap-5 p-6 sm:grid-cols-3">
              <DetailItem label="Estimated value">{formatCurrency(v.estimated_value)}</DetailItem>
              <DetailItem label="Chassis number">{v.chassis_number || "—"}</DetailItem>
              <DetailItem label="Engine size">{v.engine_cc ? `${v.engine_cc} cc` : "—"}</DetailItem>
              <DetailItem label="Seat capacity">{v.seat_capacity || "—"}</DetailItem>
              <DetailItem label="Added">{formatDate(v.created_at)}</DetailItem>
              <DetailItem label="Status"><StatusBadge status={v.is_active ? "active" : "cancelled"} label={v.is_active ? "Active" : "Inactive"} /></DetailItem>
            </div>
          </div>

          <div className="mt-7">
            <SectionTitle
              title="Documents"
              description="Logbook, certificate and vehicle photos."
              action={<Button variant="secondary" size="sm" icon={Upload} onClick={() => setDocOpen(true)}>Upload</Button>}
            />
            <div className="surface divide-y divide-ink-100">
              {documents.isError ? (
                <div className="p-4"><Alert>Could not load documents. <button type="button" className="font-semibold underline" onClick={() => documents.refetch()}>Try again</button></Alert></div>
              ) : docs.length ? docs.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between gap-3 p-4">
                  <div className="flex items-center gap-3">
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-ink-100 text-ink-500"><FileText className="h-4 w-4" /></span>
                    <div>
                      <p className="text-xs font-bold text-ink-900">{titleize(doc.document_type)}</p>
                      <p className="text-[10px] text-ink-400">{formatDate(doc.created_at)}</p>
                    </div>
                  </div>
                  <FileDownload
                    url={doc.download_url}
                    filename={doc.filename}
                    className="text-xs font-semibold text-brand-700 hover:underline"
                  >
                    Open file
                  </FileDownload>
                </div>
              )) : <p className="p-5 text-sm text-ink-500">No documents uploaded.</p>}
            </div>
          </div>

          <div className="mt-7">
            <SectionTitle title="Inspections" description="Pre-insurance and periodic vehicle inspections." action={<Button variant="secondary" size="sm" icon={CalendarCheck} onClick={() => setInspectOpen(true)}>Request inspection</Button>} />
            <div className="surface divide-y divide-ink-100">
              {inspections.isError ? (
                <div className="p-4"><Alert>Could not load inspections. <button type="button" className="font-semibold underline" onClick={() => inspections.refetch()}>Try again</button></Alert></div>
              ) : inspectionRows.length ? inspectionRows.map((inspection) => (
                <Link key={inspection.id} to={`/inspections/${inspection.id}`} className="flex items-center justify-between gap-3 p-4 transition hover:bg-ink-50/60">
                  <div>
                    <p className="text-xs font-bold text-ink-900">{inspection.inspection_number}</p>
                    <p className="mt-0.5 text-[10px] text-ink-400">{titleize(inspection.inspection_type)} · {formatDate(inspection.scheduled_at || inspection.created_at)}</p>
                  </div>
                  <StatusBadge status={inspection.status} />
                </Link>
              )) : <p className="p-5 text-sm text-ink-500">No inspections for this vehicle.</p>}
            </div>
          </div>
        </div>

        <div>
          <div className="rounded-3xl bg-gradient-to-br from-brand-600 to-brand-800 p-6 text-white">
            <ShieldCheck className="h-7 w-7 text-lime-300" />
            <p className="mt-5 font-display text-xl font-bold">Cover this vehicle</p>
            <p className="mt-2 text-sm leading-relaxed text-white/60">Request quotations from verified insurers using your vehicle value and usage.</p>
            <Link to={`/app/marketplace?vehicle=${v.id}`} className="mt-5 inline-flex"><Button variant="lime" size="sm">Compare quotes</Button></Link>
          </div>
          <div className="surface mt-5 p-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">Good to know</p>
            <ul className="mt-3 space-y-3 text-xs leading-relaxed text-ink-500">
              <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" /> Keep the estimated value close to market value. Over-insuring raises premium; under-insuring can reduce claim payouts.</li>
              <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" /> Commercial and PSV usage require commercial motor products.</li>
              <li className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" /> A pre-insurance inspection can speed up provider approval.</li>
            </ul>
          </div>
        </div>
      </div>

      <VehicleFormModal open={editOpen} onClose={() => setEditOpen(false)} vehicle={v} />

      <Modal
        open={docOpen}
        onClose={() => setDocOpen(false)}
        title="Upload vehicle document"
        footer={<><Button variant="secondary" onClick={() => setDocOpen(false)}>Cancel</Button><Button onClick={uploadDocument} loading={saving} disabled={!docFile}>Upload document</Button></>}
      >
        <form onSubmit={uploadDocument} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Select label="Document type" value={docType} onChange={(e) => setDocType(e.target.value)} options={[
            { value: "logbook", label: "Logbook" },
            { value: "insurance_certificate", label: "Insurance certificate" },
            { value: "inspection_certificate", label: "Inspection certificate" },
            { value: "photo", label: "Vehicle photo" },
            { value: "other", label: "Other" },
          ]} />
          <Input label="File" type="file" required onChange={(e) => setDocFile(e.target.files?.[0] || null)} />
        </form>
      </Modal>

      <Modal
        open={inspectOpen}
        onClose={() => setInspectOpen(false)}
        title="Request an inspection"
        description="The provider team will schedule an inspector."
        footer={<><Button variant="secondary" onClick={() => setInspectOpen(false)}>Cancel</Button><Button onClick={requestInspection} loading={saving}>Request inspection</Button></>}
      >
        <form onSubmit={requestInspection} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Select label="Inspection type" value={inspectionType} onChange={(e) => setInspectionType(e.target.value)} options={[
            { value: "pre_insurance", label: "Pre-insurance" },
            { value: "renewal", label: "Renewal" },
            { value: "periodic", label: "Periodic" },
          ]} />
          <Textarea label="Notes" value={inspectionNotes} onChange={(e) => setInspectionNotes(e.target.value)} placeholder="Anything the inspector should know?" />
        </form>
      </Modal>
    </div>
  );
}
