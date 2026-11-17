import { Alert, EmptyState, SkeletonRows } from "./ui";

export function DataTable({ columns, rows, rowKey = "id", onRowClick, empty, loading, error, onRetry, caption = "Data table" }) {
  if (loading) return <SkeletonRows rows={5} />;
  if (error) return <Alert>Could not load this list. <button className="font-semibold underline" onClick={onRetry}>Try again</button></Alert>;
  if (!rows?.length) return empty || <EmptyState title="Nothing here yet" description="Records will appear here as the workflow progresses." />;

  return (
    <div className="overflow-x-auto rounded-2xl border border-ink-100">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="table-head">
            {columns.map((column) => (
              <th scope="col" key={column.key || column.header} className={`px-4 py-3 font-semibold ${column.className || ""}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100 bg-white">
          {rows.map((row) => (
            <tr
              key={typeof rowKey === "function" ? rowKey(row) : row[rowKey]}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={onRowClick ? "cursor-pointer transition hover:bg-ink-50/70" : ""}
            >
              {columns.map((column) => (
                <td key={column.key || column.header} className={`px-4 py-3.5 align-middle ${column.cellClassName || ""}`}>
                  {column.cell ? column.cell(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DetailItem({ label, children, className }) {
  return (
    <div className={className}>
      <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-400">{label}</p>
      <div className="mt-1 text-sm font-medium text-ink-900">{children ?? "—"}</div>
    </div>
  );
}
