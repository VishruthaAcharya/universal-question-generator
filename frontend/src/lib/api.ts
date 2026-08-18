import type { Question } from "../types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function generate(
  template: File,
  source: File,
  questionCount: number,
  difficulty: string,
  score: number
) {
  const form = new FormData();
  form.append("template", template);
  form.append("source", source);
  form.append("transformation", "CET-style MCQ");
  form.append("difficulty", difficulty);
  form.append("score", String(score));
  form.append("question_count", String(questionCount));

  const res = await fetch(`${API}/api/generate`, { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
  return data as { columns: string[]; questions: Question[]; validation: unknown[] };
}

export async function regenerate(question: Question) {
  const res = await fetch(`${API}/api/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(question),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Regeneration failed");
  return data.question as Question;
}

export async function exportQuestions(questions: Question[], columns: string[], format: "csv" | "xlsx") {
  const res = await fetch(`${API}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ questions, columns, format }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail?.message || data.detail || "Export failed");
  }
  return await res.blob();
}
