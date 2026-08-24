export type QuestionRow = {
  id: string;
  row_number: number;
  data_json: Record<string, string>;
  source_answer?: string | null;
  ai_answer?: string | null;
  final_answer?: string | null;
  validation: {
    valid: boolean;
    errors: string[];
  };
  source_metadata?: {
    source_page: number | null;
    fields: Record<
      string,
      {
        origin: "extracted" | "inferred" | "missing" | "user_edited";
        confidence: number;
        reason?: string;
      }
    >;
  } | null;
  status: string;
  review_status?: "PENDING" | "APPROVED" | "FLAGGED" | "REJECTED";
  review_notes?: string;
};

export type TemplateSchema = {
  original_filename: string;
  sheet_name: string | null;
  columns: string[];
  column_schema: {
    original_name: string;
    normalized_name: string;
    required: boolean;
    example_value: string | null;
  }[];
  has_examples: boolean;
  is_archived?: boolean;
};

export type SavedTemplate = {
  id: string;
  name: string;
  original_filename: string;
  sheet_name: string | null;
  schema: TemplateSchema;
  created_at: string | null;
  usage_count: number;
  is_archived?: boolean;
  fingerprint?: string;
};

export type CompatibilityReport = {
  compatible: boolean;
  errors: { field: string; message: string }[];
  warnings: { field: string; message: string }[];
};

export interface AssessmentBatchConfig {
  assessmentName: string;
  subject: string;
  gradeClass: string;
  chapterTopic: string;
  questionType: string;
  language: string;
  targetQualityThreshold: number;
}

export type FactoryStepKey =
  | "templates"
  | "source"
  | "selection"
  | "mapping"
  | "validation"
  | "review"
  | "quality"
  | "export";

export type SelectionMode = "all" | "count" | "custom";

export interface AIFillSuggestionItem {
  value: string;
  status: "AI_INFERRED" | "UNRESOLVED";
  confidence: number;
  reason?: string;
}

export interface AIFillSuggestion {
  question_id: string;
  fields: Record<string, AIFillSuggestionItem>;
}

export interface TemplateUploadResult {
  is_duplicate: boolean;
  template_id: string;
  name: string;
  original_filename: string;
  schema: TemplateSchema;
  message?: string;
}
