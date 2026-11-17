import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck, CheckCircle2, ChevronRight, Inbox } from "lucide-react";
import api, { getErrorMessage, listData, pageCount } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { timeAgo, titleize } from "../lib/format";
import { Alert, Button, PageHeader, PageLoader, Pagination, Tabs } from "../components/ui";
import { cn } from "../components/ui";

function normalizeLink(link, role) {
  if (!link) return null;
  const customerPrefix = role === "customer" ? "/app" : "";
  const patterns = [
    [/^\/customer\/quotations\/([^/]+)$/, `${customerPrefix}/quotes/$1`],
    [/^\/customer\/applications\/([^/]+)$/, `${customerPrefix}/applications/$1`],
    [/^\/customer\/policies\/([^/]+)$/, `${customerPrefix}/policies/$1`],
    [/^\/customer\/payments\/?.*$/, `${customerPrefix}/payments`],
    [/^\/provider\/applications\/([^/]+)$/, "/provider/applications/$1"],
    [/^\/provider\/claims\/([^/]+)$/, "/claims/$1"],
  ];
  for (const [pattern, replacement] of patterns) {
    if (pattern.test(link)) return link.replace(pattern, replacement);
  }
  return link;
}

const categoryTone = {
  quotation: "bg-sky-50 text-sky-700",
  application: "bg-violet-50 text-violet-700",
  policy: "bg-emerald-50 text-emerald-700",
  payment: "bg-amber-50 text-amber-700",
  claim: "bg-red-50 text-red-700",
  inspection: "bg-indigo-50 text-indigo-700",
  organization: "bg-ink-100 text-ink-600",
};

export default function Notifications() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");

  const query = useQuery({
    queryKey: ["notifications", "list", filter, page],
    queryFn: async () => (await api.get(`/notifications/?page_size=20&page=${page}${filter === "unread" ? "&is_read=false" : filter ? "&category=" + filter : ""}`)).data,
  });
  const unread = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: async () => (await api.get("/notifications/unread-count/")).data,
  });

  const markRead = useMutation({
    mutationFn: async (notification) => (await api.post(`/notifications/${notification.id}/read/`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });
  const markAll = useMutation({
    mutationFn: async () => (await api.post("/notifications/read-all/")).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.push("All notifications marked as read.", "success");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const rows = listData(query.data);
  const total = pageCount(query.data);

  function openNotification(notification) {
    if (!notification.is_read) markRead.mutate(notification);
    const target = normalizeLink(notification.link, user?.role);
    if (target) navigate(target);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Inbox"
        title="Notifications"
        description="Quotation updates, application decisions, payment confirmations and claim activity."
        actions={<Button variant="secondary" icon={CheckCheck} onClick={() => markAll.mutate()} loading={markAll.isPending} disabled={!unread.data?.count}>Mark all read</Button>}
      />

      {error && <div className="mb-4"><Alert>{error}</Alert></div>}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Tabs active={filter} onChange={(value) => { setFilter(value); setPage(1); }} tabs={[
          { value: "", label: "All" },
          { value: "unread", label: "Unread", count: unread.data?.count },
          { value: "claim", label: "Claims" },
          { value: "payment", label: "Payments" },
          { value: "policy", label: "Policies" },
        ]} />
        <p className="text-xs text-ink-400">{unread.data?.count || 0} unread</p>
      </div>

      {query.isLoading ? <PageLoader label="Loading notifications…" /> : (
        <div className="surface divide-y divide-ink-100">
          {rows.map((notification) => (
            <button
              key={notification.id}
              onClick={() => openNotification(notification)}
              className={cn("flex w-full items-start gap-3 p-4 text-left transition hover:bg-ink-50/70 sm:p-5", !notification.is_read && "bg-brand-50/30")}
            >
              <span className={cn("mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl", categoryTone[notification.category] || categoryTone.organization)}>
                {notification.is_read ? <Bell className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-bold text-ink-900">{notification.title}</p>
                  {!notification.is_read && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-ink-500">{notification.message}</p>
                <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-wide text-ink-300">{titleize(notification.category)} · {timeAgo(notification.created_at)}</p>
              </div>
              {notification.link && <ChevronRight className="mt-2 h-4 w-4 shrink-0 text-ink-300" />}
            </button>
          ))}
          {!rows.length && (
            <div className="p-12 text-center">
              <Inbox className="mx-auto h-8 w-8 text-ink-300" />
              <p className="mt-3 text-sm font-bold text-ink-800">You&apos;re all caught up</p>
              <p className="mt-1 text-xs text-ink-400">New activity will appear here.</p>
            </div>
          )}
        </div>
      )}
      <Pagination page={page} count={total} pageSize={20} onPage={setPage} />
    </div>
  );
}
