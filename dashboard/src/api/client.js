import axios from "axios";

// Point this at the real backend once it exists, e.g. via a .env file:
// VITE_API_URL=http://localhost:5000/api
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:5000/api",
});

apiClient.interceptors.request.use((config) => {
  const stored = window.localStorage.getItem("sih26187-officer-session");
  if (stored) {
    const { token } = JSON.parse(stored);
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;
