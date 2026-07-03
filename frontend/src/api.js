import axios from "axios";

const client = axios.create({
  baseURL: "http://localhost:8000",
});

export const listDocuments = () => client.get("/documents").then(r => r.data);
export const getDocument = (id) => client.get(`/documents/${id}`).then(r => r.data);
export const markReviewed = (id, pageNumber) =>
  client.post(`/documents/${id}/pages/${pageNumber}/review`).then(r => r.data);
export const uploadDocument = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return client.post("/documents", formData).then(r => r.data);
};
export const getStats = () => client.get("/stats").then(r => r.data);
