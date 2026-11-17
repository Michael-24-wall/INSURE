import { useState } from "react";
import { downloadFile, getErrorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";

export default function FileDownload({ url, filename, children = "Open", className = "" }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function handleDownload() {
    if (!url || busy) return;
    setBusy(true);
    try {
      await downloadFile(url, filename || "document");
    } catch (error) {
      toast.push(getErrorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleDownload}
      disabled={!url || busy}
      className={`disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {busy ? "Opening..." : children}
    </button>
  );
}
