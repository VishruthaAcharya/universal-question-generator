import type {
  CompatibilityReport,
  QuestionRow,
  TemplateSchema,
  SavedTemplate,
  AIFillSuggestion,
  TemplateUploadResult,
} from "../types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function listSavedTemplates(includeArchived: boolean = false): Promise<SavedTemplate[]> {
  try {
    const res = await fetch(`${API}/api/templates?include_archived=${includeArchived}`);
    if (!res.ok) return [];
    return (await res.json()) as SavedTemplate[];
  } catch (e) {
    console.error("Failed to list saved templates:", e);
    return [];
  }
}

export async function getSavedTemplate(templateId: string): Promise<SavedTemplate> {
  const res = await fetch(`${API}/api/templates/${templateId}`);
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to fetch template");
  }
  return data as SavedTemplate;
}

export async function deleteSavedTemplate(templateId: string): Promise<{ action: string; message: string }> {
  const res = await fetch(`${API}/api/templates/${templateId}`, {
    method: "DELETE",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to delete template");
  }
  return data as { action: string; message: string };
}

export async function uploadTemplate(file: File): Promise<TemplateUploadResult> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API}/api/templates/upload`, {
    method: "POST",
    body: form,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Template upload failed");
  }
  return data as TemplateUploadResult;
}

export async function uploadSource(file: File) {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API}/api/sources/upload`, {
    method: "POST",
    body: form,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Source document upload failed");
  }
  return data as {
    source_filename: string;
    source_type: string;
    questions: Record<string, any>[];
  };
}

export async function checkCompatibility(templateId: string, questions: Record<string, any>[]) {
  const res = await fetch(`${API}/api/validate-compatibility`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template_id: templateId, questions }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Compatibility check failed");
  }
  return data as CompatibilityReport;
}

export async function aiFillMissingFields(
  questions: Record<string, any>[],
  fields: string[],
  context: Record<string, any>
): Promise<{ suggestions: AIFillSuggestion[] }> {
  const res = await fetch(`${API}/api/ai-fill-fields`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ questions, fields, context }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "AI Fill Fields failed");
  }
  return data as { suggestions: AIFillSuggestion[] };
}

export async function mapQuestions(
  templateId: string,
  questions: Record<string, any>[],
  sourceFilename: string,
  sourceType: string,
  subject: string = "General",
  context: Record<string, any> = {}
) {
  const res = await fetch(`${API}/api/map`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      template_id: templateId,
      questions,
      source_filename: sourceFilename,
      source_type: sourceType,
      subject,
      context,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Mapping failed");
  }
  return data as {
    question_set_id: string;
    template_name: string;
    columns: string[];
    questions: QuestionRow[];
  };
}

export async function updateQuestion(questionId: string, payload: Record<string, string>) {
  const res = await fetch(`${API}/api/questions/${questionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    const errorMsg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    throw new Error(errorMsg || "Question update failed");
  }
  return data as QuestionRow;
}

export async function validateAnswers(
  questions: Record<string, any>[],
  subject: string = "General",
  context: Record<string, any> = {},
  questionSetId?: string
) {
  const res = await fetch(`${API}/api/validate-answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      questions,
      subject,
      context,
      question_set_id: questionSetId,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "AI Answer Validation failed");
  }
  return data as { results: any[] };
}

export async function exportQuestionSet(questionSetId: string, format: "csv" | "xlsx") {
  const res = await fetch(`${API}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_set_id: questionSetId, format }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Export failed");
  }
  return await res.blob();
}

