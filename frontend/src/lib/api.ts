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

export async function uploadSourceTemp(file: File, batchId?: string) {
  const form = new FormData();
  form.append("file", file);
  if (batchId) {
    form.append("batch_id", batchId);
  }

  const res = await fetch(`${API}/api/sources/upload-temp`, {
    method: "POST",
    body: form,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "File upload failed");
  }
  return data as {
    batch_id: string;
    is_zip: boolean;
    extracted_files: {
      absolute_path: string;
      parent_source: string | null;
      source_file: string;
      size_bytes: number;
    }[];
    unsupported_files: {
      filename: string;
      parent_source: string | null;
      reason: string;
    }[];
  };
}

export async function processSourceBatch(
  files: {
    absolute_path: string;
    parent_source: string | null;
    source_file: string;
    size_bytes: number;
  }[],
  onProgress?: (msg: string) => void
) {
  const res = await fetch(`${API}/api/sources/process-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files }),
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Batch processing failed");
  }

  const reader = res.body?.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  if (!reader) {
    throw new Error("Response body is not readable");
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const parsed = JSON.parse(line);
        if (parsed.type === "progress" && onProgress) {
          onProgress(parsed.message);
        } else if (parsed.type === "error") {
          throw new Error(parsed.message);
        } else if (parsed.type === "result") {
          return parsed.data as {
            source_filename: string;
            source_type: string;
            questions: Record<string, any>[];
            statistics: Record<string, any>;
            warning?: string | null;
          };
        }
      } catch (e) {
        if (e instanceof Error) {
          throw e;
        }
        console.error("Failed to parse progress line:", e);
      }
    }
  }

  if (buffer.trim()) {
    try {
      const parsed = JSON.parse(buffer);
      if (parsed.type === "error") {
        throw new Error(parsed.message);
      } else if (parsed.type === "result") {
        return parsed.data as {
          source_filename: string;
          source_type: string;
          questions: Record<string, any>[];
          statistics: Record<string, any>;
          warning?: string | null;
        };
      }
    } catch (e) {
      if (e instanceof Error) {
        throw e;
      }
      console.error("Failed to parse remaining buffer:", e);
    }
  }

  throw new Error("Batch processing finished without returning a result");
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

/**
 * ONE-CLICK complete missing-field resolution for a single question.
 * The backend determines which fields are missing, makes ONE focused AI call,
 * atomically persists all resolved fields, and returns the complete updated question.
 */
export async function aiFillQuestionFields(
  questionId: string,
  context: Record<string, any>
): Promise<QuestionRow> {
  const res = await fetch(`${API}/api/questions/${questionId}/ai-fill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "AI fill question fields failed");
  }
  return data as QuestionRow;
}

/**
 * ONE-CLICK complete missing-field resolution for multiple questions (Bulk / Universal AI Fill).
 */
export async function batchAiFillQuestionFields(
  questionIds: string[],
  context: Record<string, any>
): Promise<{
  summary: {
    questions_processed: number;
    fields_filled: number;
    already_populated: number;
    needs_review: number;
    failed: number;
  };
  questions: QuestionRow[];
}> {
  const res = await fetch(`${API}/api/questions/batch-ai-fill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_ids: questionIds, context }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Batch AI fill failed");
  }
  return data;
}


export async function mapQuestions(
  templateId: string,
  questions: Record<string, any>[],
  sourceFilename: string,
  sourceType: string,
  subject: string = "General",
  context: Record<string, any> = {},
  onProgress?: (msg: string) => void
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

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Mapping failed");
  }

  const reader = res.body?.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  if (!reader) {
    throw new Error("Response body is not readable");
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const parsed = JSON.parse(line);
        if (parsed.type === "progress" && onProgress) {
          onProgress(parsed.message);
        } else if (parsed.type === "result") {
          return parsed.data as {
            question_set_id: string;
            template_name: string;
            columns: string[];
            questions: QuestionRow[];
          };
        }
      } catch (e) {
        console.error("Failed to parse progress line:", e);
      }
    }
  }

  if (buffer.trim()) {
    try {
      const parsed = JSON.parse(buffer);
      if (parsed.type === "result") {
        return parsed.data as {
          question_set_id: string;
          template_name: string;
          columns: string[];
          questions: QuestionRow[];
        };
      }
    } catch (e) {
      console.error("Failed to parse remaining buffer:", e);
    }
  }

  throw new Error("Mapping finished without returning a result");
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

export async function exportQuestionSet(
  questionSetId: string,
  format: "csv" | "xlsx",
  isDraft: boolean = false
) {
  const res = await fetch(`${API}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_set_id: questionSetId, format, is_draft: isDraft }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Export failed");
  }
  return await res.blob();
}

