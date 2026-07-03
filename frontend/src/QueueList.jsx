import { useState, useEffect } from "react";
import { listDocuments, uploadDocument, getStats } from "./api";

/**
 * Landing view: lists all processed documents with their routing decision,
 * a file upload control, and aggregate stats (auto-approval rate, etc.)
 * from the /stats endpoint.
 */
export default function QueueList({ onSelectDocument }) {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const refresh = async () => {
    try {
      const [docs, statsData] = await Promise.all([listDocuments(), getStats()]);
      setDocuments(docs);
      setStats(statsData);
    } catch (err) {
      setError("Could not reach the API. Is uvicorn still running on port 8000?");
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const handleUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      await uploadDocument(file);
      await refresh();
    } catch (err) {
      setError("Upload failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 24 }}>
      <h1>DocuVet — Review Queue</h1>

      {stats && stats.total_pages > 0 && (
        <div style={{ background: "#f5f5f5", padding: 16, borderRadius: 8, marginBottom: 24 }}>
          <strong>Pipeline stats</strong>
          <div>Total pages processed: {stats.total_pages}</div>
          <div>Auto-approval rate: {(stats.auto_approval_rate * 100).toFixed(1)}%</div>
          <div>Vision fallback rate: {(stats.vision_fallback_rate * 100).toFixed(1)}%</div>
          <div>
            Flagged by notes alone (potential false positives): {stats.flagged_by_notes_only}
            {" "}({(stats.notes_only_flag_rate * 100).toFixed(1)}%)
          </div>
        </div>
      )}

      <div style={{ marginBottom: 24 }}>
        <label style={{ display: "inline-block", padding: "8px 16px", background: "#2563eb", color: "white", borderRadius: 6, cursor: "pointer" }}>
          {uploading ? "Processing..." : "Upload document"}
          <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={handleUpload} disabled={uploading} style={{ display: "none" }} />
        </label>
        {uploading && <span style={{ marginLeft: 12, color: "#666" }}>
          Running OCR + extraction, this takes 10-20 seconds...
        </span>}
      </div>

      {error && <div style={{ color: "#dc2626", marginBottom: 16 }}>{error}</div>}

      {documents.length === 0 ? (
        <p style={{ color: "#666" }}>No documents processed yet. Upload one to get started.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
              <th style={{ padding: 8 }}>Filename</th>
              <th style={{ padding: 8 }}>Pages</th>
              <th style={{ padding: 8 }}>Decision</th>
              <th style={{ padding: 8 }}>Reviewed</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr
                key={doc.document_id}
                onClick={() => onSelectDocument(doc.document_id)}
                style={{ borderBottom: "1px solid #eee", cursor: "pointer" }}
              >
                <td style={{ padding: 8 }}>{doc.original_filename}</td>
                <td style={{ padding: 8 }}>{doc.page_count}</td>
                <td style={{ padding: 8 }}>
                  <span style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 13,
                    background: doc.decision === "auto_approved" ? "#dcfce7" : "#fef3c7",
                    color: doc.decision === "auto_approved" ? "#166534" : "#92400e",
                  }}>
                    {doc.decision}
                  </span>
                </td>
                <td style={{ padding: 8 }}>{doc.reviewed ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
