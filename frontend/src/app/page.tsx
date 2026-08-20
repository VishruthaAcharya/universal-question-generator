"use client";

import { useState, useRef, useMemo } from "react";
import type { QuestionRow, TemplateSchema, CompatibilityReport } from "../types";
import { 
  uploadTemplate, 
  uploadSource, 
  checkCompatibility, 
  mapQuestions, 
  updateQuestion, 
  exportQuestionSet 
} from "../lib/api";

type Step = "template" | "source" | "compatibility" | "review" | "export";

export default function Home() {
  const [currentStep, setCurrentStep] = useState<Step>("template");
  
  // Files and data states
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [templateId, setTemplateId] = useState<string>("");
  const [templateSchema, setTemplateSchema] = useState<TemplateSchema | null>(null);
  
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceData, setSourceData] = useState<{
    source_filename: string;
    source_type: string;
    questions: Record<string, any>[];
  } | null>(null);

  const [compatibility, setCompatibility] = useState<CompatibilityReport | null>(null);
  
  const [questionSetId, setQuestionSetId] = useState<string>("");
  const [columns, setColumns] = useState<string[]>([]);
  const [questions, setQuestions] = useState<QuestionRow[]>([]);
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [extractionProgress, setExtractionProgress] = useState<string>("");
  const [error, setError] = useState("");
  
  // Search and Filter states
  const [searchQuery, setSearchQuery] = useState("");
  const [filterValidation, setFilterValidation] = useState<"all" | "valid" | "invalid">("all");
  const [filterOrigin, setFilterOrigin] = useState<"all" | "extracted" | "inferred" | "user_edited">("all");

  const templateInputRef = useRef<HTMLInputElement>(null);
  const sourceInputRef = useRef<HTMLInputElement>(null);

  // File Upload Handlers
  async function handleTemplateChange(file: File) {
    setLoading(true);
    setError("");
    try {
      const res = await uploadTemplate(file);
      setTemplateFile(file);
      setTemplateId(res.template_id);
      setTemplateSchema(res.schema);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload template");
      setTemplateFile(null);
      setTemplateSchema(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSourceChange(file: File) {
    setLoading(true);
    setError("");
    setExtractionProgress("Reading document pages...");
    try {
      const res = await uploadSource(file);
      setSourceFile(file);
      setSourceData(res);
      setExtractionProgress("Parsing complete!");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload source");
      setSourceFile(null);
      setSourceData(null);
      setExtractionProgress("");
    } finally {
      setLoading(false);
    }
  }

  // Transitions
  async function proceedToCompatibility() {
    if (!templateId || !sourceData) return;
    setLoading(true);
    setError("");
    try {
      const report = await checkCompatibility(templateId, sourceData.questions);
      setCompatibility(report);
      setCurrentStep("compatibility");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed compatibility check");
    } finally {
      setLoading(false);
    }
  }

  async function proceedToMapping() {
    if (!templateId || !sourceData) return;
    setLoading(true);
    setError("");
    try {
      const result = await mapQuestions(
        templateId, 
        sourceData.questions, 
        sourceData.source_filename, 
        sourceData.source_type
      );
      setQuestionSetId(result.question_set_id);
      setColumns(result.columns);
      setQuestions(result.questions);
      setCurrentStep("review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to map questions");
    } finally {
      setLoading(false);
    }
  }

  // Real-time Edit Handler
  async function handleCellChange(questionId: string, columnName: string, newValue: string) {
    // Optimistic UI update
    setQuestions(prev => prev.map(q => {
      if (q.id === questionId) {
        return {
          ...q,
          data_json: {
            ...q.data_json,
            [columnName]: newValue
          },
          source_metadata: {
            source_page: q.source_metadata?.source_page ?? null,
            fields: {
              ...(q.source_metadata?.fields ?? {}),
              [columnName]: {
                origin: "user_edited",
                confidence: 1.0
              }
            }
          }
        };
      }
      return q;
    }));

    try {
      const updated = await updateQuestion(questionId, { [columnName]: newValue });
      // Apply exact validation and status from server response
      setQuestions(prev => prev.map(q => q.id === questionId ? updated : q));
    } catch (e) {
      console.error("Failed to sync edit:", e);
    }
  }

  // Export Trigger
  async function handleExport(format: "csv" | "xlsx") {
    if (!questionSetId) return;
    setLoading(true);
    setError("");
    try {
      const blob = await exportQuestionSet(questionSetId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `exported_questions_${templateSchema?.name || "set"}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setLoading(false);
    }
  }

  // Filtered Questions list
  const filteredQuestions = useMemo(() => {
    return questions.filter(q => {
      // 1. Search filter
      const textMatch = Object.values(q.data_json).some(val => 
        String(val).toLowerCase().includes(searchQuery.toLowerCase())
      );
      if (!textMatch) return false;

      // 2. Validation filter
      if (filterValidation === "valid" && !q.validation.valid) return false;
      if (filterValidation === "invalid" && q.validation.valid) return false;

      // 3. Origin filter
      if (filterOrigin !== "all") {
        const hasMatchingFieldOrigin = Object.keys(q.data_json).some(col => {
          const origin = q.source_metadata?.fields?.[col]?.origin;
          return origin === filterOrigin;
        });
        if (!hasMatchingFieldOrigin) return false;
      }

      return true;
    });
  }, [questions, searchQuery, filterValidation, filterOrigin]);

  const stepsList = [
    { key: "template", label: "Template Schema" },
    { key: "source", label: "Source Extraction" },
    { key: "compatibility", label: "Compatibility Check" },
    { key: "review", label: "Review & Edit" },
    { key: "export", label: "Export Result" }
  ];

  return (
    <main className="container">
      <header>
        <h1>Universal Question Generator</h1>
        <p className="subtitle">Deterministic template-driven question parser, validator, and review platform.</p>
      </header>

      {/* Progress Tracker */}
      <div className="steps-indicator">
        {stepsList.map((s, idx) => {
          const isCompleted = stepsList.findIndex(x => x.key === currentStep) > idx;
          const isActive = currentStep === s.key;
          return (
            <div 
              key={s.key} 
              className={`step-node ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""}`}
            >
              <div className="step-number">
                {isCompleted ? "✓" : idx + 1}
              </div>
              <span className="step-label">{s.label}</span>
            </div>
          );
        })}
      </div>

      {error && <div className="alert-panel danger">{error}</div>}

      {/* Step 1: Upload Template */}
      {currentStep === "template" && (
        <section className="card">
          <div className="card-title">
            <span className="file-icon">📋</span> Step 1: Upload Question Template
          </div>
          <p style={{ color: "var(--text-secondary)", marginBottom: "20px" }}>
            Upload an Excel (XLSX) or CSV template. This establishes the output column order, field names, and requirements.
          </p>
          
          <input 
            type="file" 
            ref={templateInputRef}
            accept=".csv,.xlsx,.xls" 
            onChange={e => e.target.files?.[0] && handleTemplateChange(e.target.files[0])} 
          />
          
          <div 
            className={`file-upload-zone ${templateFile ? "has-file" : ""}`}
            onClick={() => templateInputRef.current?.click()}
          >
            {templateFile ? (
              <>
                <span style={{ fontSize: "2.5rem" }}>📄</span>
                <strong>{templateFile.name}</strong>
                <span className="badge success">Template Uploaded Successfully</span>
              </>
            ) : (
              <>
                <span style={{ fontSize: "2.5rem" }}>📥</span>
                <strong>Drag & drop or click to browse</strong>
                <span style={{ color: "var(--text-secondary)" }}>Supports CSV, XLSX, XLS</span>
              </>
            )}
          </div>

          {templateSchema && (
            <div style={{ marginTop: "32px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ margin: 0 }}>Detected Template Columns ({templateSchema.columns.length})</h3>
                {templateSchema.sheet_name && (
                  <span className="badge info">Active Sheet: {templateSchema.sheet_name}</span>
                )}
              </div>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Column Name</th>
                      <th>Mapping Category</th>
                      <th>Mandatory</th>
                      <th>Detected Sample</th>
                    </tr>
                  </thead>
                  <tbody>
                    {templateSchema.column_schema.map((c, i) => (
                      <tr key={i}>
                        <td><strong>{c.original_name}</strong></td>
                        <td>
                          <span className={`badge ${c.original_name === c.normalized_name ? "info" : "success"}`}>
                            {c.normalized_name}
                          </span>
                        </td>
                        <td>
                          {c.required ? (
                            <span className="badge danger">Required</span>
                          ) : (
                            <span className="badge info">Optional</span>
                          )}
                        </td>
                        <td style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>
                          {c.example_value || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ marginTop: "24px", display: "flex", justifyContent: "flex-end" }}>
                <button className="primary" onClick={() => setCurrentStep("source")}>
                  Proceed to Step 2 →
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Step 2: Upload Source */}
      {currentStep === "source" && (
        <section className="card">
          <div className="card-title">
            <span className="file-icon">📚</span> Step 2: Upload Source File
          </div>
          <p style={{ color: "var(--text-secondary)", marginBottom: "20px" }}>
            Upload the source file containing questions (PDF, TXT, CSV, XLSX, DOCX, PNG, JPG, JPEG).
          </p>

          <input 
            type="file" 
            ref={sourceInputRef}
            accept=".pdf,.txt,.csv,.xlsx,.xls,.docx,.png,.jpg,.jpeg,.webp" 
            onChange={e => e.target.files?.[0] && handleSourceChange(e.target.files[0])} 
          />

          <div 
            className={`file-upload-zone ${sourceFile ? "has-file" : ""}`}
            onClick={() => sourceInputRef.current?.click()}
          >
            {sourceFile ? (
              <>
                <span style={{ fontSize: "2.5rem" }}>📄</span>
                <strong>{sourceFile.name}</strong>
                <span className="badge success">Source Loaded</span>
              </>
            ) : (
              <>
                <span style={{ fontSize: "2.5rem" }}>📥</span>
                <strong>Select source document</strong>
                <span style={{ color: "var(--text-secondary)" }}>Supports PDF, TXT, Excel, Word, CSV, Images</span>
              </>
            )}
          </div>

          {loading && extractionProgress && (
            <div style={{ marginTop: "24px", textAlign: "center", color: "var(--primary)" }}>
              <span className="spinner">⚙️</span> {extractionProgress}
            </div>
          )}

          {sourceData && (
            <div style={{ marginTop: "32px" }}>
              <div className="alert-panel success">
                <strong>Extracted Successfully!</strong>
                Found {sourceData.questions.length} question blocks in the source file.
              </div>

              <div style={{ marginTop: "24px", display: "flex", justifyContent: "space-between" }}>
                <button onClick={() => setCurrentStep("template")}>← Back to Template</button>
                <button className="primary" onClick={proceedToCompatibility} disabled={loading}>
                  {loading ? "Checking Compatibility..." : "Verify Compatibility →"}
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Step 3: Compatibility Verification */}
      {currentStep === "compatibility" && compatibility && (
        <section className="card">
          <div className="card-title">
            <span className="file-icon">⚖️</span> Step 3: Compatibility Check
          </div>

          {compatibility.compatible ? (
            <div className="alert-panel success" style={{ marginBottom: "24px" }}>
              <h3 style={{ marginBottom: "6px" }}>✓ Template and source are compatible!</h3>
              All required fields defined in your template were successfully identified or parsed from the source document.
            </div>
          ) : (
            <div className="alert-panel danger" style={{ marginBottom: "24px" }}>
              <h3 style={{ marginBottom: "6px" }}>❌ Incompatible Schema Detected</h3>
              The source file is missing required fields defined in the template. Processing is blocked.
            </div>
          )}

          <div className="row" style={{ gap: "32px", marginTop: "16px" }}>
            <div className="col-half">
              <h4 style={{ marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                Required Fields Status
              </h4>
              <ul className="list-unstyled">
                {templateSchema?.column_schema.filter(c => c.required).map((c, i) => {
                  const isMissing = compatibility.errors.some(e => e.field === c.original_name);
                  const isWarning = compatibility.warnings.some(w => w.field === c.original_name);
                  return (
                    <li key={i} style={{ color: isMissing ? "var(--danger)" : isWarning ? "var(--warning)" : "var(--accent)" }}>
                      {isMissing ? "❌" : isWarning ? "⚠️" : "✓"} {c.original_name} {isMissing ? "(Missing)" : isWarning ? "(AI will infer)" : "(Found)"}
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="col-half">
              <h4 style={{ marginBottom: "12px" }}>Warnings & Optional Fields</h4>
              {compatibility.warnings.length > 0 ? (
                <ul className="list-unstyled">
                  {compatibility.warnings.map((w, i) => (
                    <li key={i} style={{ color: "var(--warning)" }}>
                      ⚠️ {w.message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>No warnings. All fields mapped successfully.</p>
              )}
            </div>
          </div>

          <div style={{ marginTop: "40px", display: "flex", justifyContent: "space-between" }}>
            <button onClick={() => setCurrentStep("source")}>← Change Source</button>
            
            {compatibility.compatible ? (
              <button className="accent" onClick={proceedToMapping} disabled={loading}>
                {loading ? "Mapping questions..." : "Map & Continue to Review →"}
              </button>
            ) : (
              <button onClick={() => setCurrentStep("template")}>Choose Different Template</button>
            )}
          </div>
        </section>
      )}

      {/* Step 4: Dynamic Review & Edit */}
      {currentStep === "review" && (
        <section className="card" style={{ maxWidth: "100%" }}>
          <div className="card-title" style={{ justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span className="file-icon">✏️</span> Dynamic Grid Review
            </div>
            <span className="badge info">{questions.length} items parsed</span>
          </div>

          <p style={{ color: "var(--text-secondary)", marginBottom: "20px" }}>
            Review the mapped questions below. Changes are saved to PostgreSQL in real-time. Fix validation errors before exporting.
          </p>

          {/* Search and Filters Bar */}
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap", marginBottom: "24px" }}>
            <div style={{ flex: 1, minWidth: "240px" }}>
              <input 
                type="text" 
                placeholder="🔍 Search questions..." 
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
            
            <div>
              <select value={filterValidation} onChange={e => setFilterValidation(e.target.value as any)}>
                <option value="all">All Validation Statuses</option>
                <option value="valid">Valid only</option>
                <option value="invalid">Invalid only</option>
              </select>
            </div>

            <div>
              <select value={filterOrigin} onChange={e => setFilterOrigin(e.target.value as any)}>
                <option value="all">All Field Origins</option>
                <option value="extracted">Extracted from Source</option>
                <option value="inferred">AI Inferred</option>
                <option value="user_edited">User Edited</option>
              </select>
            </div>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th style={{ width: "60px" }}>Row</th>
                  <th style={{ width: "90px" }}>Source Page</th>
                  <th style={{ width: "100px" }}>Status</th>
                  {columns.map((col, idx) => (
                    <th key={idx} style={{ minWidth: "220px" }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredQuestions.map((q) => {
                  const isValid = q.validation.valid;
                  const sourcePage = q.source_metadata?.source_page;
                  return (
                    <tr key={q.id}>
                      <td style={{ textAlign: "center", fontWeight: "600" }}>{q.row_number}</td>
                      <td style={{ textAlign: "center", color: "var(--text-secondary)" }}>
                        {sourcePage ? `p. ${sourcePage}` : "—"}
                      </td>
                      <td>
                        <span 
                          className={`badge ${isValid ? "success" : "danger"}`}
                          title={q.validation.errors.join("\n")}
                          style={{ cursor: "pointer" }}
                        >
                          {isValid ? "Valid" : "Invalid"}
                        </span>
                        {!isValid && (
                          <div style={{ fontSize: "0.75rem", color: "var(--danger)", marginTop: "4px", maxWidth: "160px" }}>
                            {q.validation.errors.map((e, idx) => <div key={idx}>• {e}</div>)}
                          </div>
                        )}
                      </td>
                      {columns.map((col) => {
                        const cellVal = q.data_json[col] || "";
                        const meta = q.source_metadata?.fields?.[col];
                        const origin = meta?.origin || "missing";
                        const confidence = meta?.confidence;
                        const isDiff = col.toLowerCase().includes("difficulty");

                        return (
                          <td key={col} style={{ position: "relative" }}>
                            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                              {isDiff ? (
                                <select 
                                  value={cellVal} 
                                  onChange={e => handleCellChange(q.id, col, e.target.value)}
                                >
                                  <option value="">— Select Difficulty —</option>
                                  <option value="Easy">Easy</option>
                                  <option value="Medium">Medium</option>
                                  <option value="Hard">Hard</option>
                                  <option value="Auto">Auto</option>
                                </select>
                              ) : (
                                <textarea 
                                  rows={2}
                                  value={cellVal}
                                  onChange={e => handleCellChange(q.id, col, e.target.value)}
                                />
                              )}
                              
                              {/* Metadata/Origin details */}
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.72rem" }}>
                                {origin === "inferred" && (
                                  <span style={{ color: "var(--warning)" }} title={`Confidence: ${(confidence ?? 0 * 100).toFixed(0)}%`}>
                                    ✨ AI Inferred
                                  </span>
                                )}
                                {origin === "user_edited" && (
                                  <span style={{ color: "var(--primary-hover)" }}>
                                    ✏️ Edited
                                  </span>
                                )}
                                {origin === "missing" && cellVal === "" && (
                                  <span style={{ color: "var(--danger)", opacity: 0.7 }}>
                                    ❓ Missing
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: "32px", display: "flex", justifyContent: "space-between" }}>
            <button onClick={() => setCurrentStep("compatibility")}>← Back</button>
            <button className="primary" onClick={() => setCurrentStep("export")}>
              Proceed to Export →
            </button>
          </div>
        </section>
      )}

      {/* Step 5: Export Panel */}
      {currentStep === "export" && (
        <section className="card" style={{ textAlign: "center" }}>
          <div className="card-title" style={{ justifyContent: "center" }}>
            <span className="file-icon">💾</span> Final Export
          </div>
          
          <div style={{ margin: "24px 0" }}>
            <span style={{ fontSize: "5rem" }}>🎉</span>
          </div>

          <h2>Export Your Reviewed Questions</h2>
          <p style={{ color: "var(--text-secondary)", margin: "16px auto 32px auto", maxWidth: "500px" }}>
            The output will be formatted using your original template column order, file headers, and styles. All internal IDs are omitted.
          </p>

          {questions.some(q => !q.validation.valid) && (
            <div className="alert-panel warning" style={{ maxWidth: "600px", margin: "0 auto 24px auto" }}>
              ⚠️ <strong>Warning:</strong> You have questions with validation errors. It is highly recommended to fix them in the review table before downloading.
            </div>
          )}

          <div style={{ display: "flex", gap: "16px", justifyContent: "center" }}>
            <button className="primary" onClick={() => handleExport("xlsx")} disabled={loading}>
              Download Excel (XLSX)
            </button>
            <button className="accent" onClick={() => handleExport("csv")} disabled={loading}>
              Download CSV
            </button>
          </div>

          <div style={{ marginTop: "40px" }}>
            <button onClick={() => setCurrentStep("review")}>← Back to Editor</button>
          </div>
        </section>
      )}
    </main>
  );
}
