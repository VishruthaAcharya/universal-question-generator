"use client";

import React, { useState, useMemo } from "react";
import type { QuestionRow, AssessmentBatchConfig, AIFillSuggestion } from "../../types";
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
  const [aiSuggestions, setAiSuggestions] = useState<AIFillSuggestion[] | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [aiFillError, setAiFillError] = useState<string>("");
  const [aiSuccessNotice, setAiSuccessNotice] = useState<string>("");

  const filteredQuestions = useMemo(() => {
    return questions.filter((q) => {
      const textMatch = Object.values(q.data_json).some((val) =>
        String(val).toLowerCase().includes(searchQuery.toLowerCase())
      );
      if (!textMatch) return false;

      if (filterValidation === "valid" && !q.validation.valid) return false;
      if (filterValidation === "invalid" && q.validation.valid) return false;

      if (filterOrigin !== "all") {
        const hasMatchingFieldOrigin = Object.keys(q.data_json).some((col) => {
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
      const val = (currentQuestion.data_json[col] || "").trim();
      const isCoreStemOrOpt = [questionKey, optAKey, optBKey, optCKey, optDKey, answerKey].includes(col);
      if (!val && !isCoreStemOrOpt) {
        missing.push(col);
      }
    });
    return missing;
  }, [currentQuestion, columns, questionKey, optAKey, optBKey, optCKey, optDKey, answerKey]);

  // Handle Triggering "✨ Fill Missing Fields with AI"
  const handleTriggerAIFill = async (targetQuestionOnly: boolean = false) => {
    const questionsToProcess = targetQuestionOnly && currentQuestion
      ? [currentQuestion.data_json]
      : questions.map((q) => q.data_json);

    // Identify all missing metadata fields across target
    const fieldsToTarget: string[] = [];
    columns.forEach((col) => {
      const isCore = [questionKey, optAKey, optBKey, optCKey, optDKey, answerKey].includes(col);
      if (!isCore) fieldsToTarget.push(col);
    });

    if (fieldsToTarget.length === 0 || questionsToProcess.length === 0) return;

    setIsAiFilling(true);
    setAiFillError("");
    setAiSuccessNotice("");
    try {
      const res = await aiFillMissingFields(questionsToProcess, fieldsToTarget, {
        subject: batchConfig.subject,
        gradeClass: batchConfig.gradeClass,
        chapterTopic: batchConfig.chapterTopic,
        questionType: batchConfig.questionType,
      });
      setAiSuggestions(res.suggestions);
      setPreviewOpen(true);
    } catch (e) {
      setAiFillError(e instanceof Error ? e.message : "AI Infill failed");
    } finally {
      setIsAiFilling(false);
    }
  };

  // Accept all suggestions
  const handleAcceptAllSuggestions = () => {
    if (!aiSuggestions) return;
    aiSuggestions.forEach((sug, i) => {
      const q = questions[i];
      if (q) {
        Object.entries(sug.fields).forEach(([fname, fval]) => {
          if (fval.value && fval.status === "AI_INFERRED") {
            onCellChange(q.id, fname, fval.value);
          }
        });
      }
    });
    setPreviewOpen(false);
    setAiSuccessNotice(`Successfully applied AI metadata suggestions across ${aiSuggestions.length} questions.`);
  };

  // Accept single field suggestion
  const handleAcceptField = (questionIndex: number, fieldName: string, value: string) => {
    const q = questions[questionIndex];
    if (q && value) {
      onCellChange(q.id, fieldName, value);
      // Remove from pending suggestions
      if (aiSuggestions && aiSuggestions[questionIndex]) {
        const updated = [...aiSuggestions];
        delete updated[questionIndex].fields[fieldName];
        setAiSuggestions(updated);
      }
    }
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
              <span className={`badge ${currentQuestion.validation.valid ? "success" : "danger"}`} style={{ gap: "4px" }}>
                {currentQuestion.validation.valid ? <CheckIcon size={12} /> : <XIcon size={12} />}
                {currentQuestion.validation.valid ? "VALID" : "ISSUES FOUND"}
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
                <SparklesIcon size={15} /> ✨ Fill Missing Fields with AI
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
                <FileTextIcon size={16} color="var(--primary-hover)" /> Source Extraction Context
              </div>

              <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                Document: <strong style={{ color: "var(--text-primary)" }}>{sourceFilename || "Source Ingested"}</strong>
              </div>

              <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                Source Page: <strong style={{ color: "var(--text-primary)" }}>
                  {currentQuestion.source_metadata?.source_page ? `Page ${currentQuestion.source_metadata.source_page}` : "Extracted Section"}
                </strong>
              </div>

              {/* Authoritative Source Answer vs AI Answer */}
              <div style={{ background: "rgba(0,0,0,0.25)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                <div style={{ fontSize: "0.74rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700, marginBottom: "6px" }}>
                  Answer Integrity Check
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.84rem" }}>
                  <span>Source Answer:</span>
                  <strong style={{ color: currentQuestion.data_json[answerKey] ? "var(--text-primary)" : "var(--danger)" }}>
                    {currentQuestion.data_json[answerKey] || "MISSING"}
                  </strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "4px" }}>
                  <span>Status:</span>
                  <span style={{ color: currentQuestion.validation.valid ? "var(--accent)" : "var(--danger)" }}>
                    {currentQuestion.validation.valid ? "✓ Parity Verified" : "⚠ Conflict Detected"}
                  </span>
                </div>
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
                      <SparklesIcon size={14} /> ✨ Fill Missing Fields with AI
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
                    const confidence = meta?.confidence ?? 1.0;

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
                  value={currentQuestion.data_json[questionKey] || ""}
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
                      value={currentQuestion.data_json[k] || ""}
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
                      value={currentQuestion.data_json[answerKey] || ""}
                      onChange={(e) => onCellChange(currentQuestion.id, answerKey, e.target.value)}
                      placeholder="e.g. A, B, Option 1..."
                    />
                  </div>
                )}

                {columns.includes(difficultyKey) && (
                  <div>
                    <label>Difficulty Level</label>
                    <select
                      value={currentQuestion.data_json[difficultyKey] || ""}
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
                          value={currentQuestion.data_json[col] || ""}
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
              <SparklesIcon size={16} /> ✨ Fill Missing Fields with AI
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
      {previewOpen && aiSuggestions && (
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

            <div style={{ display: "flex", flexDirection: "column", gap: "12px", margin: "16px 0" }}>
              {aiSuggestions.map((sug, i) => {
                const questionPrompt = questions[i]?.data_json[questionKey] || `Question #${i + 1}`;
                const hasFields = Object.keys(sug.fields).length > 0;
                if (!hasFields) return null;

                return (
                  <div
                    key={i}
                    style={{
                      background: "var(--bg-surface)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "10px",
                      padding: "16px",
                    }}
                  >
                    <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: "6px", color: "var(--primary-hover)" }}>
                      Q{i + 1}: <span style={{ color: "var(--text-primary)", fontWeight: 400 }}>{questionPrompt}</span>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "10px", marginTop: "10px" }}>
                      {Object.entries(sug.fields).map(([fname, fval]) => (
                        <div key={fname} style={{ background: "rgba(0,0,0,0.25)", padding: "10px 12px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
                          <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", fontWeight: 600 }}>{fname}</div>
                          <div style={{ fontWeight: 700, fontSize: "0.92rem", color: "var(--text-primary)", margin: "4px 0" }}>
                            {fval.value || "—"}
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.7rem", color: "var(--warning)" }}>
                            <span>Confidence: {(fval.confidence * 100).toFixed(0)}%</span>
                            <button
                              className="accent"
                              onClick={() => handleAcceptField(i, fname, fval.value)}
                              style={{ padding: "2px 8px", fontSize: "0.7rem" }}
                            >
                              Accept
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
              <button className="secondary" onClick={() => setPreviewOpen(false)}>
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
