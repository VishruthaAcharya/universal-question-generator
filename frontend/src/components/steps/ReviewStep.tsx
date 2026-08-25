"use client";

import React, { useState, useMemo } from "react";
import type {
  QuestionRow,
  AssessmentBatchConfig,
  NormalizedQuestionSuggestion,
  NormalizedFieldSuggestion,
} from "../../types";
import { aiFillMissingFields } from "../../lib/api";
import ReviewTable from "../ReviewTable";
import AlertPanel from "../AlertPanel";
import {
  ReviewIcon,
  SparklesIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  CheckIcon,
  XIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  EditIcon,
  FileTextIcon,
} from "../icons";

interface ReviewStepProps {
  columns: string[];
  questions: QuestionRow[];
  sourceFilename: string;
  batchConfig: AssessmentBatchConfig;
  onCellChange: (questionId: string, columnName: string, newValue: string) => void;
  onBack: () => void;
  onNext: () => void;
}

/**
 * Robust normalizer for /ai-fill-fields response.
 * Safely parses any response contract variant (nested objects, flat records, suggestions arrays, string values)
 * into a typed NormalizedQuestionSuggestion structure.
 */
export function normalizeAISuggestions(
  rawResponse: unknown,
  targetQuestions: QuestionRow[],
  columns: string[],
  questionKey: string
): NormalizedQuestionSuggestion[] {
  if (!rawResponse || typeof rawResponse !== "object") return [];

  let list: unknown[] = [];
  const rawObj = rawResponse as Record<string, unknown>;

  if (Array.isArray(rawObj.suggestions)) {
    list = rawObj.suggestions;
  } else if (Array.isArray(rawResponse)) {
    list = rawResponse;
  } else if (rawObj.fields && typeof rawObj.fields === "object") {
    list = [rawObj];
  } else {
    list = [rawObj];
  }

  const result: NormalizedQuestionSuggestion[] = [];

  list.forEach((item, itemIdx) => {
    if (!item || typeof item !== "object") return;
    const itemObj = item as Record<string, any>;

    // Find matching question row from targetQuestions
    let matchedQuestion = targetQuestions.find(
      (q) =>
        (itemObj.question_id && String(q.id) === String(itemObj.question_id)) ||
        (itemObj.id && String(q.id) === String(itemObj.id))
    );

    if (!matchedQuestion && typeof itemObj.row_number === "number") {
      matchedQuestion = targetQuestions.find((q) => q.row_number === itemObj.row_number);
    }

    if (!matchedQuestion && itemIdx < targetQuestions.length) {
      matchedQuestion = targetQuestions[itemIdx];
    }

    const questionId = matchedQuestion?.id || itemObj.question_id || itemObj.id || `q-${itemIdx + 1}`;
    const rowNumber = matchedQuestion?.row_number ?? (itemIdx + 1);
    const questionPrompt =
      matchedQuestion?.data_json?.[questionKey] ||
      (matchedQuestion?.row_number ? `Question #${matchedQuestion.row_number}` : `Question #${itemIdx + 1}`);

    const fieldsMap: Record<string, NormalizedFieldSuggestion> = {};

    const addField = (fname: string, fval: any) => {
      if (!fname || fval === null || fval === undefined) return;
      let val = "";
      let status: "AI_INFERRED" | "UNRESOLVED" = "AI_INFERRED";
      let confidence = 0.95;
      let reason: string | undefined;

      if (typeof fval === "object") {
        val = String(fval.value ?? fval.val ?? fval.text ?? "").trim();
        status = fval.status === "UNRESOLVED" ? "UNRESOLVED" : "AI_INFERRED";
        if (typeof fval.confidence === "number" && !isNaN(fval.confidence)) {
          confidence = fval.confidence > 1 ? fval.confidence / 100 : fval.confidence;
        }
        if (typeof fval.reason === "string" && fval.reason.trim()) {
          reason = fval.reason.trim();
        }
      } else if (typeof fval === "string" || typeof fval === "number") {
        val = String(fval).trim();
      }

      if (val && val !== "null" && val !== "undefined" && status !== "UNRESOLVED") {
        fieldsMap[fname] = {
          fieldName: fname,
          value: val,
          status,
          confidence: Math.min(1, Math.max(0, confidence)),
          reason,
          isEditing: false,
          editValue: val,
        };
      }
    };

    // Case 1: item has a `fields` object
    if (itemObj.fields && typeof itemObj.fields === "object" && !Array.isArray(itemObj.fields)) {
      Object.entries(itemObj.fields).forEach(([fname, fval]) => {
        addField(fname, fval);
      });
    }
    // Case 2: item has a `suggestions` array
    else if (Array.isArray(itemObj.suggestions)) {
      itemObj.suggestions.forEach((subItem: any) => {
        if (subItem && typeof subItem === "object") {
          const fieldName = subItem.field || subItem.fieldName || subItem.name;
          if (fieldName) addField(fieldName, subItem);
        }
      });
    }
    // Case 3: item is a single suggestion: { field: "Topic", value: "...", confidence: 0.95 }
    else if (itemObj.field && (itemObj.value !== undefined || itemObj.val !== undefined)) {
      addField(String(itemObj.field), itemObj);
    }
    // Case 4: item is flat object with field keys
    else {
      Object.entries(itemObj).forEach(([k, v]) => {
        if (
          ["question_id", "id", "row_number", "status", "validation", "source_metadata", "prompt"].includes(k)
        ) {
          return;
        }
        if (columns.includes(k) || (typeof v === "object" && v !== null && ("value" in v || "confidence" in v))) {
          addField(k, v);
        }
      });
    }

    if (Object.keys(fieldsMap).length > 0) {
      const existing = result.find((r) => r.questionId === questionId);
      if (existing) {
        existing.fields = { ...existing.fields, ...fieldsMap };
      } else {
        result.push({
          questionId,
          rowNumber,
          questionPrompt,
          fields: fieldsMap,
        });
      }
    }
  });

  return result;
}

export default function ReviewStep({
  columns,
  questions,
  sourceFilename,
  batchConfig,
  onCellChange,
  onBack,
  onNext,
}: ReviewStepProps) {
  const [viewMode, setViewMode] = useState<"studio" | "grid">("studio");
  const [currentIndex, setCurrentIndex] = useState(0);

  // Filters for Grid
  const [searchQuery, setSearchQuery] = useState("");
  const [filterValidation, setFilterValidation] = useState<"all" | "valid" | "invalid">("all");
  const [filterOrigin, setFilterOrigin] = useState<"all" | "extracted" | "inferred" | "user_edited">("all");

  // AI Fill States
  const [isAiFilling, setIsAiFilling] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<NormalizedQuestionSuggestion[] | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [aiFillError, setAiFillError] = useState<string>("");
  const [aiSuccessNotice, setAiSuccessNotice] = useState<string>("");

  const filteredQuestions = useMemo(() => {
    return questions.filter((q) => {
      const textMatch = Object.values(q.data_json || {}).some((val) =>
        String(val || "").toLowerCase().includes(searchQuery.toLowerCase())
      );
      if (!textMatch) return false;

      if (filterValidation === "valid" && !q.validation?.valid) return false;
      if (filterValidation === "invalid" && q.validation?.valid) return false;

      if (filterOrigin !== "all") {
        const hasMatchingFieldOrigin = Object.keys(q.data_json || {}).some((col) => {
          const origin = q.source_metadata?.fields?.[col]?.origin;
          return origin === filterOrigin;
        });
        if (!hasMatchingFieldOrigin) return false;
      }

      return true;
    });
  }, [questions, searchQuery, filterValidation, filterOrigin]);

  const currentQuestion = questions[currentIndex] || questions[0];

  const findColumnKey = (pattern: RegExp, fallback = "") => {
    return columns.find((c) => pattern.test(c)) || fallback;
  };

  const questionKey = findColumnKey(/question|item_text|prompt/i, columns[0] || "");
  const optAKey = findColumnKey(/option.*a|choice.*a|answer.*1/i, "Option A");
  const optBKey = findColumnKey(/option.*b|choice.*b|answer.*2/i, "Option B");
  const optCKey = findColumnKey(/option.*c|choice.*c|answer.*3/i, "Option C");
  const optDKey = findColumnKey(/option.*d|choice.*d|answer.*4/i, "Option D");
  const answerKey = findColumnKey(/answer|correct/i, "Correct Answer");
  const difficultyKey = findColumnKey(/difficulty|level/i, "Difficulty");
  const topicKey = findColumnKey(/topic|chapter/i, "Topic");
  const bloomsKey = findColumnKey(/bloom/i, "Bloom's Taxonomy");

  // Identify missing metadata fields for current question
  const currentMissingFields = useMemo(() => {
    if (!currentQuestion) return [];
    const missing: string[] = [];
    columns.forEach((col) => {
      const val = (currentQuestion.data_json?.[col] || "").trim();
      const isCoreStemOrOpt = [questionKey, optAKey, optBKey, optCKey, optDKey, answerKey].includes(col);
      if (!val && !isCoreStemOrOpt) {
        missing.push(col);
      }
    });
    return missing;
  }, [currentQuestion, columns, questionKey, optAKey, optBKey, optCKey, optDKey, answerKey]);

  // Suggestions specifically for current question
  const currentQuestionSuggestions = useMemo(() => {
    if (!currentQuestion || !aiSuggestions) return null;
    return aiSuggestions.find((s) => s.questionId === currentQuestion.id) || null;
  }, [currentQuestion, aiSuggestions]);

  // Handle Triggering "✨ Fill Missing Fields with AI"
  const handleTriggerAIFill = async (targetQuestionOnly: boolean = false) => {
    const targetQuestions =
      targetQuestionOnly && currentQuestion ? [currentQuestion] : questions;

    const questionsToProcess = targetQuestions.map((q) => ({
      id: q.id,
      question_id: q.id,
      row_number: q.row_number,
      ...(q.data_json || {}),
    }));

    // Identify all missing metadata fields across target
    const fieldsToTarget: string[] = [];
    columns.forEach((col) => {
      const isCore = [questionKey, optAKey, optBKey, optCKey, optDKey, answerKey].includes(col);
      if (!isCore) fieldsToTarget.push(col);
    });

    if (fieldsToTarget.length === 0 || questionsToProcess.length === 0) {
      setAiSuccessNotice("No eligible missing metadata fields found to infill.");
      return;
    }

    setIsAiFilling(true);
    setAiFillError("");
    setAiSuccessNotice("");

    try {
      const res = await aiFillMissingFields(questionsToProcess, fieldsToTarget, {
        subject: batchConfig.subject || "General",
        gradeClass: batchConfig.gradeClass || "General",
        chapterTopic: batchConfig.chapterTopic || "General",
        questionType: batchConfig.questionType || "Multiple Choice (MCQ)",
      });

      const normalized = normalizeAISuggestions(res, targetQuestions, columns, questionKey);

      if (normalized.length === 0 || normalized.every((q) => Object.keys(q.fields).length === 0)) {
        setAiSuggestions(null);
        setPreviewOpen(false);
        setAiSuccessNotice("No eligible missing fields were found for AI inference.");
      } else {
        setAiSuggestions(normalized);
        setPreviewOpen(true);
      }
    } catch (e) {
      let safeMsg = "AI field inference failed. Please try again.";
      if (e instanceof Error && e.message) {
        const clean = e.message.replace(/https?:\/\/[^\s]+/g, "").replace(/[a-zA-Z0-9]{32,}/g, "***");
        if (clean.length < 150) {
          safeMsg = clean;
        }
      }
      setAiFillError(safeMsg);
    } finally {
      setIsAiFilling(false);
    }
  };

  // Accept single field suggestion
  const handleAcceptField = (questionId: string, fieldName: string, value: string) => {
    if (!questionId || !fieldName || !value) return;

    // Apply to authoritative question data
    onCellChange(questionId, fieldName, value);

    // Remove from pending suggestions
    if (aiSuggestions) {
      const updated = aiSuggestions
        .map((qs) => {
          if (qs.questionId === questionId) {
            const nextFields = { ...qs.fields };
            delete nextFields[fieldName];
            return { ...qs, fields: nextFields };
          }
          return qs;
        })
        .filter((qs) => Object.keys(qs.fields).length > 0);

      if (updated.length === 0) {
        setAiSuggestions(null);
        setPreviewOpen(false);
        setAiSuccessNotice(`Accepted AI suggestion for ${fieldName}. All suggestions processed.`);
      } else {
        setAiSuggestions(updated);
      }
    }
  };

  // Reject single field suggestion
  const handleRejectField = (questionId: string, fieldName: string) => {
    if (!aiSuggestions) return;

    const updated = aiSuggestions
      .map((qs) => {
        if (qs.questionId === questionId) {
          const nextFields = { ...qs.fields };
          delete nextFields[fieldName];
          return { ...qs, fields: nextFields };
        }
        return qs;
      })
      .filter((qs) => Object.keys(qs.fields).length > 0);

    if (updated.length === 0) {
      setAiSuggestions(null);
      setPreviewOpen(false);
    } else {
      setAiSuggestions(updated);
    }
  };

  // Toggle field editing mode in preview modal
  const handleToggleEdit = (questionId: string, fieldName: string, isEditing: boolean) => {
    if (!aiSuggestions) return;
    setAiSuggestions((prev) =>
      prev
        ? prev.map((qs) => {
            if (qs.questionId === questionId && qs.fields[fieldName]) {
              return {
                ...qs,
                fields: {
                  ...qs.fields,
                  [fieldName]: {
                    ...qs.fields[fieldName],
                    isEditing,
                    editValue: qs.fields[fieldName].value,
                  },
                },
              };
            }
            return qs;
          })
        : null
    );
  };

  // Change edited value in preview modal
  const handleEditValueChange = (questionId: string, fieldName: string, val: string) => {
    if (!aiSuggestions) return;
    setAiSuggestions((prev) =>
      prev
        ? prev.map((qs) => {
            if (qs.questionId === questionId && qs.fields[fieldName]) {
              return {
                ...qs,
                fields: {
                  ...qs.fields,
                  [fieldName]: {
                    ...qs.fields[fieldName],
                    editValue: val,
                  },
                },
              };
            }
            return qs;
          })
        : null
    );
  };

  // Save edited value and accept
  const handleSaveAndAcceptEdit = (questionId: string, fieldName: string) => {
    if (!aiSuggestions) return;
    const targetQ = aiSuggestions.find((qs) => qs.questionId === questionId);
    const field = targetQ?.fields[fieldName];
    const finalVal = (field?.editValue ?? field?.value ?? "").trim();
    if (finalVal) {
      handleAcceptField(questionId, fieldName, finalVal);
    }
  };

  // Accept all suggestions across all questions
  const handleAcceptAllSuggestions = () => {
    if (!aiSuggestions || aiSuggestions.length === 0) return;

    let appliedCount = 0;
    aiSuggestions.forEach((qs) => {
      Object.entries(qs.fields).forEach(([fname, fval]) => {
        if (fval.value && fval.status === "AI_INFERRED") {
          onCellChange(qs.questionId, fname, fval.value);
          appliedCount += 1;
        }
      });
    });

    setAiSuggestions(null);
    setPreviewOpen(false);
    setAiSuccessNotice(`Successfully applied ${appliedCount} AI metadata suggestion${appliedCount === 1 ? "" : "s"}.`);
  };

  // Reject all suggestions and close modal
  const handleRejectAllAndClose = () => {
    setAiSuggestions(null);
    setPreviewOpen(false);
  };

  return (
    <section className="card" style={{ maxWidth: "100%" }}>
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <ReviewIcon size={22} color="var(--primary-hover)" /> Step 6: Human Review & AI-Assisted Workspace
          </div>
          <div className="card-subtitle">
            Authoritative human review workspace. Inspect source page origins, verify answer parity, and leverage AI to infill missing metadata.
          </div>
        </div>

        {/* View Mode Toggle */}
        <div style={{ display: "flex", gap: "8px", background: "var(--bg-surface)", padding: "4px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
          <button
            className={viewMode === "studio" ? "primary" : "secondary"}
            onClick={() => setViewMode("studio")}
            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
          >
            Studio Split View
          </button>
          <button
            className={viewMode === "grid" ? "primary" : "secondary"}
            onClick={() => setViewMode("grid")}
            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
          >
            Tabular Grid View
          </button>
        </div>
      </div>

      {aiSuccessNotice && (
        <AlertPanel type="success" style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <CheckCircleIcon size={16} /> {aiSuccessNotice}
            </span>
            <button className="secondary" onClick={() => setAiSuccessNotice("")} style={{ padding: "2px 6px", fontSize: "0.7rem" }}>
              ✕
            </button>
          </div>
        </AlertPanel>
      )}

      {aiFillError && (
        <AlertPanel type="danger" style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <AlertTriangleIcon size={16} /> {aiFillError}
            </span>
            <button className="secondary" onClick={() => setAiFillError("")} style={{ padding: "2px 6px", fontSize: "0.7rem" }}>
              ✕
            </button>
          </div>
        </AlertPanel>
      )}

      {/* STUDIO MODE (Source vs Extracted vs AI Assist vs Final) */}
      {viewMode === "studio" && currentQuestion && (
        <div>
          {/* Stepper Bar & Batch AI Fill Trigger */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "16px",
              background: "var(--bg-surface)",
              padding: "10px 16px",
              borderRadius: "8px",
              border: "1px solid var(--border-subtle)",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>
                Question {currentIndex + 1} of {questions.length}
              </span>
              <span className={`badge ${currentQuestion.validation?.valid ? "success" : "danger"}`} style={{ gap: "4px" }}>
                {currentQuestion.validation?.valid ? <CheckIcon size={12} /> : <XIcon size={12} />}
                {currentQuestion.validation?.valid ? "VALID" : "ISSUES FOUND"}
              </span>
              {currentQuestion.source_metadata?.source_page && (
                <span className="badge info">Page {currentQuestion.source_metadata.source_page}</span>
              )}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {/* Prominent Global AI Fill Action */}
              <button
                className="accent"
                onClick={() => handleTriggerAIFill(false)}
                disabled={isAiFilling}
                style={{ padding: "6px 14px", fontSize: "0.82rem", gap: "6px" }}
              >
                <SparklesIcon size={15} /> {isAiFilling ? "Inferring Missing Fields..." : "✨ Fill Missing Fields with AI"}
              </button>

              <div style={{ display: "flex", gap: "6px" }}>
                <button
                  className="secondary"
                  disabled={currentIndex === 0}
                  onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                  style={{ padding: "6px 12px", fontSize: "0.8rem", gap: "4px" }}
                >
                  <ArrowLeftIcon size={14} /> Prev
                </button>
                <button
                  className="secondary"
                  disabled={currentIndex === questions.length - 1}
                  onClick={() => setCurrentIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                  style={{ padding: "6px 12px", fontSize: "0.8rem", gap: "4px" }}
                >
                  Next <ArrowRightIcon size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Split Container */}
          <div className="review-studio-container">
            {/* Left Column: SOURCE CONTEXT & AI INFILL HUB */}
            <div className="studio-source-panel">
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, fontSize: "0.9rem", color: "var(--text-primary)" }}>
              {/* Cross-Page Traceability & Source Context */}
              <div style={{ background: "rgba(0,0,0,0.2)", padding: "10px 12px", borderRadius: "8px", border: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", gap: "4px" }}>
                <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  Document: <strong style={{ color: "var(--text-primary)" }}>{sourceFilename || "Source Ingested"}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.76rem" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Question Location:</span>
                  <strong style={{ color: "var(--text-primary)" }}>
                    {currentQuestion.source_metadata?.source_page ? `Page ${currentQuestion.source_metadata.source_page}` : "Extracted Section"}
                  </strong>
                </div>
                {currentQuestion.answer_page && (
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.76rem" }}>
                    <span style={{ color: "var(--text-secondary)" }}>Answer Key Location:</span>
                    <strong style={{ color: "var(--accent)" }}>
                      Page {currentQuestion.answer_page} ({currentQuestion.answer_section || "Answer Key"})
                    </strong>
                  </div>
                )}
                {currentQuestion.mapping_confidence !== undefined && (
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.74rem", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "4px", marginTop: "2px" }}>
                    <span style={{ color: "var(--text-muted)" }}>Mapping Trace:</span>
                    <span style={{ color: currentQuestion.mapping_confidence >= 0.90 ? "var(--accent)" : "var(--warning)" }}>
                      {currentQuestion.answer_source || "EXPLICIT_ANSWER_KEY"} · {(currentQuestion.mapping_confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
                {currentQuestion.mapping_reason && (
                  <div style={{ fontSize: "0.70rem", color: "var(--text-muted)", fontStyle: "italic", lineHeight: "1.3" }}>
                    {currentQuestion.mapping_reason}
                  </div>
                )}
              </div>

              {/* Authoritative Source Answer vs AI Answer & Conflict Resolution Hub */}
              <div style={{ background: "rgba(0,0,0,0.25)", padding: "14px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "0.74rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700, marginBottom: "8px", display: "flex", justifyContent: "space-between" }}>
                  <span>Answer Parity & AI Confidence</span>
                  {currentQuestion.validation?.ai_validation?.confidence !== undefined && (
                    <span style={{ color: "var(--primary-hover)" }}>
                      {(currentQuestion.validation.ai_validation.confidence * 100).toFixed(0)}% AI Confidence
                    </span>
                  )}
                </div>

                {/* Source Answer Row */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.84rem", marginBottom: "6px" }}>
                  <span style={{ color: "var(--text-secondary)" }}>
                    Source Key {currentQuestion.answer_page ? `(p. ${currentQuestion.answer_page})` : ""}:
                  </span>
                  <strong style={{ color: (currentQuestion.source_answer || currentQuestion.data_json?.[answerKey]) ? "var(--text-primary)" : "var(--danger)" }}>
                    {currentQuestion.source_answer || currentQuestion.data_json?.[answerKey] || "MISSING"}
                  </strong>
                </div>

                {/* AI Solution Row */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.84rem", marginBottom: "6px" }}>
                  <span style={{ color: "var(--text-secondary)" }}>AI Solution:</span>
                  <strong style={{ color: "var(--primary-hover)" }}>
                    {currentQuestion.ai_answer || currentQuestion.validation?.ai_validation?.ai_answer || "—"}
                  </strong>
                </div>

                {/* Status Row */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "4px" }}>
                  <span>Parity Status:</span>
                  <span style={{ color: currentQuestion.validation?.valid ? "var(--accent)" : "var(--danger)", fontWeight: 700 }}>
                    {currentQuestion.validation?.valid ? "✓ Parity Verified" : "✕ Answer Conflict"}
                  </span>
                </div>

                {/* Rationale */}
                {currentQuestion.validation?.ai_validation?.reason && (
                  <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: "8px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "6px", lineHeight: "1.4" }}>
                    <em>{currentQuestion.validation.ai_validation.reason}</em>
                  </div>
                )}

                {/* Conflict Resolution Actions */}
                {(!currentQuestion.validation?.valid || (currentQuestion.source_answer && currentQuestion.ai_answer && currentQuestion.source_answer.toUpperCase() !== currentQuestion.ai_answer.toUpperCase())) && (
                  <div style={{ marginTop: "12px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "6px", padding: "8px" }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--danger)", fontWeight: 700, marginBottom: "6px" }}>
                      Resolve Discrepancy:
                    </div>
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                      {currentQuestion.source_answer && (
                        <button
                          className="secondary"
                          onClick={() => {
                            if (currentQuestion.source_answer) {
                              onCellChange(currentQuestion.id, answerKey, currentQuestion.source_answer);
                            }
                          }}
                          style={{ padding: "3px 8px", fontSize: "0.72rem", flex: "1 1 auto" }}
                        >
                          Accept Source ({currentQuestion.source_answer})
                        </button>
                      )}
                      {currentQuestion.ai_answer && (
                        <button
                          className="accent"
                          onClick={() => {
                            if (currentQuestion.ai_answer) {
                              onCellChange(currentQuestion.id, answerKey, currentQuestion.ai_answer);
                            }
                          }}
                          style={{ padding: "3px 8px", fontSize: "0.72rem", flex: "1 1 auto" }}
                        >
                          Accept AI ({currentQuestion.ai_answer})
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Missing Metadata & AI Infill Box */}
              <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <span style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    Metadata Infill
                  </span>
                  {currentMissingFields.length > 0 && (
                    <span className="badge warning">{currentMissingFields.length} Missing</span>
                  )}
                </div>

                {/* Inline Pending AI Suggestions for Current Question */}
                {currentQuestionSuggestions && Object.keys(currentQuestionSuggestions.fields).length > 0 && (
                  <div style={{ marginBottom: "14px", background: "rgba(124, 58, 237, 0.08)", border: "1px solid rgba(124, 58, 237, 0.3)", borderRadius: "8px", padding: "10px" }}>
                    <div style={{ fontSize: "0.76rem", fontWeight: 700, color: "var(--primary-hover)", display: "flex", alignItems: "center", gap: "5px", marginBottom: "8px" }}>
                      <SparklesIcon size={14} /> Pending AI Suggestions
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {Object.entries(currentQuestionSuggestions.fields).map(([fname, fval]) => (
                        <div key={fname} style={{ background: "rgba(0,0,0,0.3)", padding: "8px", borderRadius: "6px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--text-secondary)" }}>{fname}</span>
                            <span style={{ fontSize: "0.68rem", color: "var(--warning)" }}>
                              AI_INFERRED · {(fval.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div style={{ fontWeight: 700, fontSize: "0.86rem", color: "var(--text-primary)", margin: "3px 0" }}>
                            {fval.value}
                          </div>
                          <div style={{ display: "flex", gap: "6px", marginTop: "6px" }}>
                            <button
                              className="accent"
                              onClick={() => handleAcceptField(currentQuestion.id, fname, fval.value)}
                              style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                            >
                              Accept
                            </button>
                            <button
                              className="secondary"
                              onClick={() => handleRejectField(currentQuestion.id, fname)}
                              style={{ padding: "2px 6px", fontSize: "0.7rem" }}
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {currentMissingFields.length > 0 ? (
                  <div style={{ marginBottom: "12px" }}>
                    <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
                      {currentMissingFields.map((f) => (
                        <span key={f} style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.25)", color: "#FDE68A", padding: "2px 8px", borderRadius: "4px", fontSize: "0.72rem" }}>
                          {f}
                        </span>
                      ))}
                    </div>

                    <button
                      className="accent"
                      onClick={() => handleTriggerAIFill(true)}
                      disabled={isAiFilling}
                      style={{ width: "100%", padding: "8px 12px", fontSize: "0.82rem", gap: "6px" }}
                    >
                      <SparklesIcon size={14} /> {isAiFilling ? "Inferring..." : "✨ Fill Missing Fields with AI"}
                    </button>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "6px", lineHeight: "1.4" }}>
                      AI will infer eligible missing fields from the source content. Review suggestions before applying.
                    </div>
                  </div>
                ) : (
                  <div style={{ fontSize: "0.78rem", color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px" }}>
                    <CheckCircleIcon size={14} /> All schema metadata fields populated.
                  </div>
                )}
              </div>

              {/* Field Origins Breakdown */}
              <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "12px" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "8px" }}>
                  Field Origins & Confidences:
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  {columns.map((col) => {
                    const meta = currentQuestion.source_metadata?.fields?.[col];
                    const origin = meta?.origin || "extracted";
                    const confidence = typeof meta?.confidence === "number" ? meta.confidence : 1.0;

                    return (
                      <div
                        key={col}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "0.73rem",
                          padding: "3px 6px",
                          background: "rgba(0,0,0,0.15)",
                          borderRadius: "4px",
                        }}
                      >
                        <span style={{ color: "var(--text-muted)", maxWidth: "150px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {col}
                        </span>
                        <span style={{ color: origin === "inferred" ? "var(--warning)" : origin === "user_edited" ? "var(--primary-hover)" : "var(--accent)" }}>
                          {origin === "inferred" ? `AI (${(confidence * 100).toFixed(0)}%)` : origin === "user_edited" ? "Edited" : "Source"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Right Column: QUESTION EDITOR FORM */}
            <div className="studio-editor-panel">
              <div>
                <label>Question Prompt / Stem ({questionKey})</label>
                <textarea
                  rows={4}
                  value={currentQuestion.data_json?.[questionKey] || ""}
                  onChange={(e) => onCellChange(currentQuestion.id, questionKey, e.target.value)}
                  placeholder="Enter question statement..."
                />
              </div>

              {/* MCQ Options */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                {[optAKey, optBKey, optCKey, optDKey].filter((k) => columns.includes(k)).map((k, idx) => (
                  <div key={k}>
                    <label>{k}</label>
                    <input
                      type="text"
                      value={currentQuestion.data_json?.[k] || ""}
                      onChange={(e) => onCellChange(currentQuestion.id, k, e.target.value)}
                      placeholder={`Option ${String.fromCharCode(65 + idx)} text`}
                    />
                  </div>
                ))}
              </div>

              {/* Answer & Difficulty */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                {columns.includes(answerKey) && (
                  <div>
                    <label>Correct Answer Key (Authoritative)</label>
                    <input
                      type="text"
                      value={currentQuestion.data_json?.[answerKey] || ""}
                      onChange={(e) => onCellChange(currentQuestion.id, answerKey, e.target.value)}
                      placeholder="e.g. A, B, Option 1..."
                    />
                  </div>
                )}

                {columns.includes(difficultyKey) && (
                  <div>
                    <label>Difficulty Level</label>
                    <select
                      value={currentQuestion.data_json?.[difficultyKey] || ""}
                      onChange={(e) => onCellChange(currentQuestion.id, difficultyKey, e.target.value)}
                    >
                      <option value="">— Select Difficulty —</option>
                      <option value="Easy">Easy</option>
                      <option value="Medium">Medium</option>
                      <option value="Hard">Hard</option>
                      <option value="Auto">Auto / Unspecified</option>
                    </select>
                  </div>
                )}
              </div>

              {/* Metadata Fields (Topic, Bloom's, Score, etc.) */}
              {columns.filter((c) => ![questionKey, optAKey, optBKey, optCKey, optDKey, answerKey, difficultyKey].includes(c)).length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
                  {columns
                    .filter((c) => ![questionKey, optAKey, optBKey, optCKey, optDKey, answerKey, difficultyKey].includes(c))
                    .map((col) => (
                      <div key={col}>
                        <label>{col}</label>
                        <input
                          type="text"
                          value={currentQuestion.data_json?.[col] || ""}
                          onChange={(e) => onCellChange(currentQuestion.id, col, e.target.value)}
                        />
                      </div>
                    ))}
                </div>
              )}

              {/* Action Bar */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingTop: "16px",
                  borderTop: "1px solid var(--border-subtle)",
                  marginTop: "auto",
                }}
              >
                <button
                  className="accent"
                  onClick={() => {
                    if (currentIndex < questions.length - 1) {
                      setCurrentIndex((prev) => prev + 1);
                    }
                  }}
                  style={{ gap: "6px" }}
                >
                  <CheckIcon size={14} /> Approve & Next Question
                </button>

                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  Changes sync to database in real-time
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* GRID MODE */}
      {viewMode === "grid" && (
        <div>
          <div
            style={{
              display: "flex",
              gap: "14px",
              flexWrap: "wrap",
              marginBottom: "20px",
              alignItems: "center",
            }}
          >
            <div style={{ flex: 1, minWidth: "240px" }}>
              <input
                type="text"
                placeholder="Search questions, options, answers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            <div style={{ width: "180px" }}>
              <select
                value={filterValidation}
                onChange={(e) => setFilterValidation(e.target.value as any)}
              >
                <option value="all">All Validation Statuses</option>
                <option value="valid">Valid only</option>
                <option value="invalid">Invalid only</option>
              </select>
            </div>

            <div style={{ width: "180px" }}>
              <select
                value={filterOrigin}
                onChange={(e) => setFilterOrigin(e.target.value as any)}
              >
                <option value="all">All Origins</option>
                <option value="extracted">Extracted from Source</option>
                <option value="inferred">AI Inferred</option>
                <option value="user_edited">User Edited</option>
              </select>
            </div>

            <button
              className="accent"
              onClick={() => handleTriggerAIFill(false)}
              disabled={isAiFilling}
              style={{ padding: "10px 16px", fontSize: "0.85rem", gap: "6px" }}
            >
              <SparklesIcon size={16} /> {isAiFilling ? "Inferring Missing Fields..." : "✨ Fill Missing Fields with AI"}
            </button>
          </div>

          <ReviewTable
            columns={columns}
            questions={filteredQuestions}
            onCellChange={onCellChange}
          />
        </div>
      )}

      {/* AI SUGGESTIONS PREVIEW MODAL */}
      {previewOpen && aiSuggestions && aiSuggestions.length > 0 && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-card-solid)",
              border: "1px solid var(--border-medium)",
              borderRadius: "16px",
              padding: "28px",
              maxWidth: "840px",
              width: "100%",
              maxHeight: "85vh",
              overflowY: "auto",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div>
                <h3 style={{ margin: 0, fontWeight: 800, display: "flex", alignItems: "center", gap: "8px" }}>
                  <SparklesIcon size={20} color="var(--primary-hover)" /> AI Metadata Suggestions Preview
                </h3>
                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                  Review proposals before applying to ensure accuracy. Source answers remain authoritative.
                </div>
              </div>
              <button className="secondary" onClick={() => setPreviewOpen(false)} style={{ padding: "4px 8px" }}>
                <XIcon size={16} />
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px", margin: "16px 0" }}>
              {aiSuggestions.map((qs) => {
                const fieldEntries = Object.entries(qs.fields || {});
                if (fieldEntries.length === 0) return null;

                return (
                  <div
                    key={qs.questionId}
                    style={{
                      background: "var(--bg-surface)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "10px",
                      padding: "16px",
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: "6px", color: "var(--primary-hover)" }}>
                      Q{qs.rowNumber}: <span style={{ color: "var(--text-primary)", fontWeight: 400 }}>{qs.questionPrompt}</span>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "12px", marginTop: "10px" }}>
                      {fieldEntries.map(([fname, fval]) => (
                        <div
                          key={fname}
                          style={{
                            background: "rgba(0,0,0,0.25)",
                            padding: "12px",
                            borderRadius: "8px",
                            border: "1px solid var(--border-subtle)",
                            display: "flex",
                            flexDirection: "column",
                            justifyContent: "space-between",
                            gap: "8px",
                          }}
                        >
                          <div>
                            <div style={{ fontSize: "0.74rem", color: "var(--text-secondary)", fontWeight: 600, textTransform: "uppercase" }}>
                              {fname}
                            </div>

                            {fval.isEditing ? (
                              <div style={{ marginTop: "6px" }}>
                                <input
                                  type="text"
                                  value={fval.editValue ?? fval.value}
                                  onChange={(e) => handleEditValueChange(qs.questionId, fname, e.target.value)}
                                  style={{ width: "100%", padding: "6px 8px", fontSize: "0.85rem", marginBottom: "6px" }}
                                  autoFocus
                                />
                                <div style={{ display: "flex", gap: "6px" }}>
                                  <button
                                    className="accent"
                                    onClick={() => handleSaveAndAcceptEdit(qs.questionId, fname)}
                                    style={{ padding: "3px 8px", fontSize: "0.72rem" }}
                                  >
                                    Save & Accept
                                  </button>
                                  <button
                                    className="secondary"
                                    onClick={() => handleToggleEdit(qs.questionId, fname, false)}
                                    style={{ padding: "3px 8px", fontSize: "0.72rem" }}
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <>
                                <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text-primary)", margin: "4px 0" }}>
                                  {fval.value || "—"}
                                </div>
                                <div style={{ fontSize: "0.72rem", color: "var(--warning)", display: "flex", alignItems: "center", gap: "4px" }}>
                                  <span>AI_INFERRED · {(Number(fval.confidence ?? 0.95) * 100).toFixed(0)}% confidence</span>
                                </div>
                                {fval.reason && (
                                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "4px", fontStyle: "italic" }}>
                                    {fval.reason}
                                  </div>
                                )}
                              </>
                            )}
                          </div>

                          {!fval.isEditing && (
                            <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "8px" }}>
                              <button
                                className="accent"
                                onClick={() => handleAcceptField(qs.questionId, fname, fval.value)}
                                style={{ padding: "3px 10px", fontSize: "0.74rem" }}
                              >
                                Accept
                              </button>
                              <button
                                className="secondary"
                                onClick={() => handleToggleEdit(qs.questionId, fname, true)}
                                style={{ padding: "3px 8px", fontSize: "0.74rem", gap: "3px" }}
                              >
                                <EditIcon size={12} /> Edit
                              </button>
                              <button
                                className="secondary"
                                onClick={() => handleRejectField(qs.questionId, fname)}
                                style={{ padding: "3px 8px", fontSize: "0.74rem" }}
                              >
                                Reject
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
              <button className="secondary" onClick={handleRejectAllAndClose}>
                Reject All & Close
              </button>

              <button className="accent" onClick={handleAcceptAllSuggestions} style={{ gap: "6px" }}>
                <CheckIcon size={16} /> Accept All Suggestions
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer Navigation */}
      <div
        style={{
          marginTop: "32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to AI Validation
        </button>

        <button className="primary" onClick={onNext} style={{ gap: "6px" }}>
          Proceed to Quality Dashboard <ArrowRightIcon size={16} />
        </button>
      </div>
    </section>
  );
}
