import client from "./client";

export async function register({ email, full_name, password }) {
  const { data } = await client.post("/auth/register", { email, full_name, password });
  return data;
}

export async function login({ email, password }) {
  const { data } = await client.post("/auth/login", { email, password });
  return data;
}

export async function me() {
  const { data } = await client.get("/auth/me");
  return data;
}
