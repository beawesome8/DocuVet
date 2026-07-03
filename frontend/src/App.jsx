import { useState } from "react";
import QueueList from "./QueueList";
import DocumentDetail from "./DocumentDetail";

export default function App() {
  const [selectedDocId, setSelectedDocId] = useState(null);

  return selectedDocId ? (
    <DocumentDetail documentId={selectedDocId} onBack={() => setSelectedDocId(null)} />
  ) : (
    <QueueList onSelectDocument={setSelectedDocId} />
  );
}
