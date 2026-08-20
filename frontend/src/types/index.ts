export type QuestionRow = {
  id: string;
  row_number: number;
  data_json: Record<string, string>;
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
      }
    >;
  } | null;
  status: string;
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
};

export type CompatibilityReport = {
  compatible: boolean;
  errors: { field: string; message: string }[];
  warnings: { field: string; message: string }[];
};
