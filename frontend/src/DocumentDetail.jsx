import { useState, useEffect } from "react";
import { getDocument, markReviewed } from "./api";

/**
 * Detail view for one document: shows each page's image alongside its
 * extracted fields, the routing decision and why, and a mark-reviewed
 * control. Click-to-highlight source regions on the image is a named
 * scope cut (see README) - this shows the full image and full field
 * list side by side, no bounding-box interaction.
 */
export default function DocumentDetail({ documentId, onBack }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);

  const refresh = async () => {
    try {
      const data = await getDocument(documentId);
      setDoc(data);
    } catch (err) {
      setError("Could not load document.");
    }
  };

  useEffect(() => {
    refresh();
  }, [documentId]);

  const handleMarkReviewed = async (pageNumber) => {
    await markReviewed(documentId, pageNumber);
    await refresh();
  };

  if (error) return <div style={{ padding: 24, color: "#dc2626" }}>{error}</div>;
  if (!doc) return <div style={{ padding: 24 }}>Loading...</div>;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 24 }}>
      <button onClick={onBack} style={{ marginBottom: 16 }}>← Back to queue</button>
      <h2>{doc.original_filename}</h2>

      {doc.pages.map((page) => (
        <div key={page.page_number} style={{ display: "flex", gap: 24, marginBottom: 32, border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
          <div style={{ flex: 1 }}>
            <img
              src={`http://localhost:8000${page.image_url}`}
              alt={`Page ${page.page_number}`}
              style={{ width: "100%", border: "1px solid #eee" }}
            />
          </div>

          <div style={{ flex: 1 }}>
            <div style={{
              display: "inline-block",
              padding: "4px 10px",
              borderRadius: 4,
              marginBottom: 12,
              background: page.decision === "auto_approved" ? "#dcfce7" : "#fef3c7",
              color: page.decision === "auto_approved" ? "#166534" : "#92400e",
              fontWeight: 600,
            }}>
              {page.decision}
            </div>

            <div style={{ fontSize: 13, color: "#666", marginBottom: 16 }}>
              {page.decision_reasons.map((reason, i) => (
                <div key={i}>• {reason}</div>
              ))}
            </div>

            <table style={{ width: "100%", fontSize: 14 }}>
              <tbody>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Vendor</td><td>{page.extraction.vendor_name}</td></tr>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Invoice #</td><td>{page.extraction.invoice_number}</td></tr>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Invoice date</td><td>{page.extraction.invoice_date}</td></tr>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Due date</td><td>{page.extraction.due_date || "—"}</td></tr>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Subtotal</td><td>€{page.extraction.subtotal?.toFixed(2)}</td></tr>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Tax</td><td>€{page.extraction.tax_amount?.toFixed(2)}</td></tr>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Total</td><td>€{page.extraction.total_amount?.toFixed(2)}</td></tr>
                <tr><td style={{ color: "#666", padding: "4px 0" }}>Extraction method</td><td>{page.extraction.extraction_method}</td></tr>
              </tbody>
            </table>

            <div style={{ marginTop: 12 }}>
              <strong style={{ fontSize: 13 }}>Line items</strong>
              <ul style={{ fontSize: 13, paddingLeft: 18 }}>
                {page.extraction.line_items.map((item, i) => (
                  <li key={i}>
                    {item.description} — qty {item.quantity ?? "?"}, unit {item.unit_price ?? "N/A"}, total €{item.line_total?.toFixed(2)}
                  </li>
                ))}
              </ul>
            </div>

            {page.extraction.extraction_notes && (
              <div style={{ marginTop: 12, fontSize: 13, background: "#fef3c7", padding: 8, borderRadius: 4 }}>
                <strong>Model notes:</strong> {page.extraction.extraction_notes}
              </div>
            )}

            <button
              onClick={() => handleMarkReviewed(page.page_number)}
              disabled={page.reviewed}
              style={{ marginTop: 16, padding: "8px 16px", background: page.reviewed ? "#d1d5db" : "#2563eb", color: "white", border: "none", borderRadius: 6, cursor: page.reviewed ? "default" : "pointer" }}
            >
              {page.reviewed ? "Reviewed ✓" : "Mark as reviewed"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
