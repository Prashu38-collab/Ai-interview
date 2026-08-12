import axios from "axios";

// Use the Vite dev-server proxy in development (/api -> backend).
// In production (nginx) the same relative proxy is used, so no CORS is needed.
const BASE_URL = "/api";

const client = axios.create({ baseURL: BASE_URL });

// Attach the JWT to every request.
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear the session and bounce to the login page.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// Small helper to surface a friendly error message from the API.
export function errorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg).join("; ");
  }
  return error.message || "Something went wrong.";
}

export default client;
