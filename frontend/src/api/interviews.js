import client from "./client";

export async function createInterview(payload) {
  const { data } = await client.post("/interviews", payload);
  return data;
}

export async function listInterviews() {
  const { data } = await client.get("/interviews");
  return data;
}

export async function getInterview(id) {
  const { data } = await client.get(`/interviews/${id}`);
  return data;
}

export async function analyzeInterview(id) {
  const { data } = await client.post(`/interviews/${id}/analyze`);
  return data;
}

export async function generateQuestions(id, difficulty) {
  const { data } = await client.post(`/interviews/${id}/generate-questions`, {
    difficulty,
  });
  return data;
}

export async function getQuestions(id) {
  const { data } = await client.get(`/interviews/${id}/questions`);
  return data;
}

export async function submitAnswer(questionId, text) {
  const { data } = await client.post(`/questions/${questionId}/answer`, { text });
  return data;
}

export async function completeInterview(id) {
  const { data } = await client.post(`/interviews/${id}/complete`);
  return data;
}

export async function getReport(id) {
  const { data } = await client.get(`/interviews/${id}/report`);
  return data;
}
