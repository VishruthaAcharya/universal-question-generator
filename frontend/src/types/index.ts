export interface AIValidationResult {
  question_id: string;
  row_number?: number;
  ai_answer: string | null;
  ai_answer_text: string | null;
  source_answer: string | null;
  source_answer_text?: string | null;
  answer_match: boolean | null;
  confidence: number;
  confidence_level: "HIGH" | "MEDIUM" | "LOW" | "UNCERTAIN";
  validation_status: "AI_VALIDATED" | "ANSWER_CONFLICT" | "AMBIGUOUS" | "MISSING_INFORMATION" | "VISUAL_CONTEXT_REQUIRED" | "UNCERTAIN" | "AI_SOLVED_NO_SOURCE" | "AI_ACCEPTED" | "SOURCE_ACCEPTED";
  validation_methods: string[];
  review_required: boolean;
  review_priority: number;
  reason: string;
  subject?: string;
  signals?: {
    solver_agreed?: boolean;
    critic_agreed?: boolean;
    deterministic_verified?: boolean;
    extraction_confidence?: number;
    option_count?: number;
    defects_detected?: string[];
  };
}

export type QuestionRow = {
  id: string;
  row_number: number;
  data_json: Record<string, string>;
  source_answer?: string | null;
  ai_answer?: string | null;
  ai_answer_text?: string | null;
  final_answer?: string | null;
  answer_source?: "EXPLICIT_ANSWER_KEY" | "QUESTION_TEXT" | "STRUCTURED_SOURCE" | "AI_SEMANTIC_MAPPING" | "AI_SUGGESTED" | "HUMAN_ENTERED" | "MISSING" | string | null;
  answer_page?: number | null;
  answer_section?: string | null;
  mapping_confidence?: number;
  answer_mapping_status?: "ANSWER_MAPPED" | "ANSWER_KEY_DETECTED" | "AMBIGUOUS_MAPPING" | "MISSING_ANSWER" | string;
  mapping_reason?: string | null;
  validation: {
    valid: boolean;
    errors: string[];
    ai_validation?: AIValidationResult;
  };
  source_metadata?: {
    source_page: number | null;
    answer_source?: string;
    answer_page?: number | null;
    answer_section?: string | null;
    mapping_confidence?: number;
    answer_mapping_status?: string;
    mapping_reason?: string | null;
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
  question_id?: string;
  id?: string;
  row_number?: number;
  fields?: Record<string, AIFillSuggestionItem>;
  field?: string;
  value?: string;
  confidence?: number;
  status?: string;
  origin?: string;
  suggestions?: any[];
  [key: string]: any;
}

export interface NormalizedFieldSuggestion {
  fieldName: string;
  value: string;
  status: "AI_INFERRED" | "UNRESOLVED";
  confidence: number;
  reason?: string;
  isEditing?: boolean;
  editValue?: string;
}

export interface NormalizedQuestionSuggestion {
  questionId: string;
  rowNumber: number;
  questionPrompt: string;
  fields: Record<string, NormalizedFieldSuggestion>;
}

export interface TemplateUploadResult {
  is_duplicate: boolean;
  template_id: string;
  name: string;
  original_filename: string;
  schema: TemplateSchema;
  message?: string;
}
