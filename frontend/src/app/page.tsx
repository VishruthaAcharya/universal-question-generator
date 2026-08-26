"use client";

import { useState } from "react";
import type {
  QuestionRow,
  TemplateSchema,
  SavedTemplate,
  CompatibilityReport,
  AssessmentBatchConfig,
  FactoryStepKey,
  AIFillSuggestion,
} from "../types";
import {
  uploadSource,
  checkCompatibility,
  mapQuestions,
  updateQuestion,
  exportQuestionSet,
} from "../lib/api";
import MenntrAppShell from "../components/MenntrAppShell";
import AlertPanel from "../components/AlertPanel";
import TemplateStep from "../components/steps/TemplateStep";
import SourceStep from "../components/steps/SourceStep";
import QuestionSelectionStep from "../components/steps/QuestionSelectionStep";
import CompatibilityStep from "../components/steps/CompatibilityStep";
import ValidationStep from "../components/steps/ValidationStep";
import ReviewStep from "../components/steps/ReviewStep";
import QualityDashboardStep from "../components/steps/QualityDashboardStep";
import ExportStep from "../components/steps/ExportStep";

export default function Home() {
  // Primary Workflow Navigation (8 Steps)
  const [currentStep, setCurrentStep] = useState<FactoryStepKey>("templates");

  // Assessment Details Configuration
  const [batchConfig, setBatchConfig] = useState<AssessmentBatchConfig>({
    assessmentName: "Grade 10 Mathematics Periodic Assessment",
    subject: "Mathematics",
    gradeClass: "Class 10",
    chapterTopic: "Unit 4: Quadratic Equations",
    questionType: "Multiple Choice (MCQ)",
    language: "English",
    targetQualityThreshold: 100,
  });

  // Template / Schema State
  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [templateId, setTemplateId] = useState<string>("");
  const [templateName, setTemplateName] = useState<string>("");
  const [templateSchema, setTemplateSchema] = useState<TemplateSchema | null>(null);

  // Source Document & Raw Extracted Questions
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceData, setSourceData] = useState<{
    source_filename: string;
    source_type: string;
    questions: Record<string, any>[];
  } | null>(null);

  // All extracted raw questions (e.g. 28 detected)
  const [rawQuestions, setRawQuestions] = useState<Record<string, any>[]>([]);
  // Indices of user-selected questions
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);

  // Compatibility & Mapping
  const [compatibility, setCompatibility] = useState<CompatibilityReport | null>(null);
  const [questionSetId, setQuestionSetId] = useState<string>("");
  const [columns, setColumns] = useState<string[]>([]);
  const [questions, setQuestions] = useState<QuestionRow[]>([]);

  // UI States
  const [loading, setLoading] = useState(false);
  const [extractionProgress, setExtractionProgress] = useState<string>("");
  const [mappingProgress, setMappingProgress] = useState<string>("");
  const [error, setError] = useState<string>("");

  // Handler: Selected Template from Registry or Custom Upload
  function handleTemplateSelected(id: string, name: string, schema: TemplateSchema) {
    setTemplateId(id);
    setTemplateName(name);
    setTemplateSchema(schema);
  }

  // Handler: Source Upload & Complete Extraction
  async function handleSourceUpload(file: File) {
    setLoading(true);
    setError("");
    setExtractionProgress("Extracting text nodes, OCR scanning, and detecting ALL question blocks...");
    try {
      const res = await uploadSource(file);
      setSourceFile(file);
      setSourceData(res);
      setRawQuestions(res.questions || []);
      // Default to selecting ALL detected questions
      const allIndices = (res.questions || []).map((_, i) => i);
      setSelectedIndices(allIndices);
      setExtractionProgress("Extraction complete!");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to parse source document");
      setSourceFile(null);
      setSourceData(null);
      setRawQuestions([]);
      setSelectedIndices([]);
      setExtractionProgress("");
    } finally {
      setLoading(false);
    }
  }

  // Get active questions subset based on user selection
  const getSelectedQuestions = () => {
    return selectedIndices.map((idx) => rawQuestions[idx]).filter(Boolean);
  };

  // Handler: Compatibility Check for Selected Questions
  async function proceedToCompatibility() {
    if (!templateId || selectedIndices.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const activeQuestions = getSelectedQuestions();
      const report = await checkCompatibility(templateId, activeQuestions);
      setCompatibility(report);
      setCurrentStep("mapping");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Schema compatibility check failed");
    } finally {
      setLoading(false);
    }
  }

  // Handler: Execute AI Mapping
  async function proceedToMapping() {
    if (!templateId || selectedIndices.length === 0) return;
    setLoading(true);
    setError("");
    setMappingProgress("Mapping source fields...");
    try {
      const activeQuestions = getSelectedQuestions();
      const result = await mapQuestions(
        templateId,
        activeQuestions,
        sourceData?.source_filename || sourceFile?.name || "source_file",
        sourceData?.source_type || "pdf",
        batchConfig.subject || "General",
        {
          gradeClass: batchConfig.gradeClass,
          chapterTopic: batchConfig.chapterTopic,
          questionType: batchConfig.questionType,
        },
        (msg) => setMappingProgress(msg)
      );
      setQuestionSetId(result.question_set_id);
      setColumns(result.columns);
      setQuestions(result.questions);
      setCurrentStep("validation");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Question mapping failed");
    } finally {
      setLoading(false);
      setMappingProgress("");
    }
  }

  // Handler: Cell Edit Sync (and AI Fill acceptances)
  async function handleCellChange(questionId: string, columnName: string, newValue: string) {
    setQuestions((prev) =>
      prev.map((q) => {
        if (q.id === questionId) {
          return {
            ...q,
            data_json: {
              ...q.data_json,
              [columnName]: newValue,
            },
            source_metadata: {
              source_page: q.source_metadata?.source_page ?? null,
              fields: {
                ...(q.source_metadata?.fields ?? {}),
                [columnName]: {
                  origin: "user_edited",
                  confidence: 1.0,
                },
              },
            },
          };
        }
        return q;
      })
    );

    try {
      const updated = await updateQuestion(questionId, { [columnName]: newValue });
      setQuestions((prev) => prev.map((q) => (q.id === questionId ? updated : q)));
    } catch (e) {
      console.error("Cell update sync error:", e);
    }
  }

  // Handler: Export
  async function handleExport(format: "csv" | "xlsx") {
    if (!questionSetId) return;
    setLoading(true);
    setError("");
    try {
      const blob = await exportQuestionSet(questionSetId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeTitle = (batchConfig.assessmentName || "menntr_assessment").replace(/\s+/g, "_").toLowerCase();
      a.download = `${safeTitle}_export.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assessment export failed");
    } finally {
      setLoading(false);
    }
  }

  const validQuestionsCount = questions.filter((q) => q.validation.valid).length;

  return (
    <MenntrAppShell
      currentStep={currentStep}
      onNavigate={(step) => setCurrentStep(step)}
      batchConfig={batchConfig}
      onUpdateBatchConfig={setBatchConfig}
      totalDetected={rawQuestions.length}
      totalSelected={selectedIndices.length}
      validQuestions={validQuestionsCount}
      hasSource={Boolean(sourceData)}
      hasSchema={Boolean(templateSchema)}
      hasMapped={questions.length > 0}
    >
      {error && (
        <AlertPanel type="danger" style={{ marginBottom: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>{error}</span>
            <button
              className="secondary"
              onClick={() => setError("")}
              style={{ padding: "2px 8px", fontSize: "0.75rem" }}
            >
              Dismiss
            </button>
          </div>
        </AlertPanel>
      )}

      {/* Step 1: Template Registry & Schema */}
      {currentStep === "templates" && (
        <TemplateStep
          templateFile={templateFile}
          templateId={templateId}
          templateSchema={templateSchema}
          onTemplateSelected={handleTemplateSelected}
          onNext={() => setCurrentStep("source")}
        />
      )}

      {/* Step 2: Source Files Upload & Full Extraction */}
      {currentStep === "source" && (
        <SourceStep
          sourceFile={sourceFile}
          sourceData={sourceData}
          loading={loading}
          extractionProgress={extractionProgress}
          onSourceChange={handleSourceUpload}
          onBack={() => setCurrentStep("templates")}
          onNext={() => setCurrentStep("selection")}
        />
      )}

      {/* Step 3: Question Selection & Subsetting */}
      {currentStep === "selection" && (
        <QuestionSelectionStep
          rawQuestions={rawQuestions}
          selectedIndices={selectedIndices}
          onSelectionChange={setSelectedIndices}
          onBack={() => setCurrentStep("source")}
          onNext={() => {
            if (!templateId) {
              setCurrentStep("templates");
            } else {
              proceedToCompatibility();
            }
          }}
        />
      )}

      {/* Step 4: Schema Field Mapping & Compatibility */}
      {currentStep === "mapping" && compatibility && (
        <CompatibilityStep
          compatibility={compatibility}
          templateSchema={templateSchema}
          selectedQuestionsCount={selectedIndices.length}
          loading={loading}
          mappingProgress={mappingProgress}
          onBack={() => setCurrentStep("selection")}
          onChangeTemplate={() => setCurrentStep("templates")}
          onProceedToMapping={proceedToMapping}
        />
      )}

      {/* Step 5: AI Validation Dashboard */}
      {currentStep === "validation" && (
        <ValidationStep
          questions={questions}
          columns={columns}
          onProceedToReview={() => setCurrentStep("review")}
          onBack={() => setCurrentStep("mapping")}
        />
      )}

      {/* Step 6: Human Review & AI-Assisted Workspace */}
      {currentStep === "review" && (
        <ReviewStep
          columns={columns}
          questions={questions}
          sourceFilename={sourceData?.source_filename || sourceFile?.name || ""}
          batchConfig={batchConfig}
          onCellChange={handleCellChange}
          onQuestionsUpdate={(updatedQuestions) => setQuestions(updatedQuestions)}
          onBack={() => setCurrentStep("validation")}
          onNext={() => setCurrentStep("quality")}
        />
      )}

      {/* Step 7: Quality Dashboard & Quality Gate */}
      {currentStep === "quality" && (
        <QualityDashboardStep
          questions={questions}
          batchConfig={batchConfig}
          onProceedToExport={() => setCurrentStep("export")}
          onJumpToReview={() => setCurrentStep("review")}
          onBack={() => setCurrentStep("review")}
        />
      )}

      {/* Step 8: Final Export & Publishing */}
      {currentStep === "export" && (
        <ExportStep
          batchConfig={batchConfig}
          templateName={templateName}
          totalQuestions={questions.length}
          hasValidationErrors={questions.some((q) => !q.validation.valid)}
          loading={loading}
          onExport={handleExport}
          onBack={() => setCurrentStep("quality")}
        />
      )}
    </MenntrAppShell>
  );
}
