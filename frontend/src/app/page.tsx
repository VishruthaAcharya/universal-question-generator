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
  uploadSourceTemp,
  processSourceBatch,
  checkCompatibility,
  mapQuestions,
  updateQuestion,
  exportQuestionSet,
} from "../lib/api";
import type { BatchFileItem } from "../components/steps/SourceStep";
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

  // Source Documents & Raw Extracted Questions
  const [files, setFiles] = useState<BatchFileItem[]>([]);
  const [batchId, setBatchId] = useState<string>("");
  const [sourceData, setSourceData] = useState<{
    source_filename: string;
    source_type: string;
    questions: Record<string, any>[];
    statistics?: Record<string, any>;
    warning?: string | null;
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

  // Config limits matching backend defaults
  const MAX_SINGLE_FILE_SIZE_MB = 25;
  const MAX_ZIP_SIZE_MB = 50;
  const MAX_FILES_PER_BATCH = 20;

  // Handler: Selected Template from Registry or Custom Upload
  function handleTemplateSelected(id: string, name: string, schema: TemplateSchema) {
    setTemplateId(id);
    setTemplateName(name);
    setTemplateSchema(schema);
  }

  // Helper to generate unique local IDs
  const generateId = () => Math.random().toString(36).substring(2, 9);

  // Handler: Add files to state and upload them
  async function handleAddFiles(newFiles: File[]) {
    if (files.length + newFiles.length > MAX_FILES_PER_BATCH) {
      setError(`Maximum batch limit is ${MAX_FILES_PER_BATCH} files.`);
      return;
    }

    let activeBatchId = batchId;
    if (!activeBatchId) {
      const generated = Math.random().toString(36).substring(2, 15);
      setBatchId(generated);
      activeBatchId = generated;
    }

    // Validate limits
    const validatedFiles: File[] = [];
    for (const f of newFiles) {
      const ext = f.name.split(".").pop()?.toLowerCase();
      if (ext === "zip") {
        if (f.size > MAX_ZIP_SIZE_MB * 1024 * 1024) {
          setError(`${f.name} exceeds the maximum ZIP size of ${MAX_ZIP_SIZE_MB} MB.`);
          return;
        }
      } else {
        if (f.size > MAX_SINGLE_FILE_SIZE_MB * 1024 * 1024) {
          setError(`${f.name} exceeds the maximum size of ${MAX_SINGLE_FILE_SIZE_MB} MB.`);
          return;
        }
      }
      validatedFiles.push(f);
    }

    setError("");

    // Create file items in pending state
    const newItems: BatchFileItem[] = validatedFiles.map((f) => ({
      id: generateId(),
      name: f.name,
      size: f.size,
      status: "pending",
      progress: 0,
    }));

    setFiles((prev) => [...prev, ...newItems]);

    // Upload each file asynchronously
    for (let i = 0; i < validatedFiles.length; i++) {
      const file = validatedFiles[i];
      const item = newItems[i];

      setFiles((prev) =>
        prev.map((f) => (f.id === item.id ? { ...f, status: "uploading", progress: 20 } : f))
      );

      try {
        const res = await uploadSourceTemp(file, activeBatchId);
        
        if (res.is_zip) {
          // Replace zip item with extracted files
          const extractedItems: BatchFileItem[] = res.extracted_files.map((ef) => ({
            id: generateId(),
            name: ef.source_file,
            size: ef.size_bytes,
            status: "success",
            progress: 100,
            absolute_path: ef.absolute_path,
            parent_source: ef.parent_source,
          }));

          const unsupportedItems: BatchFileItem[] = res.unsupported_files.map((uf) => ({
            id: generateId(),
            name: uf.filename,
            size: 0,
            status: "error",
            progress: 100,
            error: uf.reason,
            parent_source: uf.parent_source,
          }));

          setFiles((prev) => {
            const listWithoutZip = prev.filter((f) => f.id !== item.id);
            return [...listWithoutZip, ...extractedItems, ...unsupportedItems];
          });
        } else {
          // Regular file
          const singleFile = res.extracted_files[0];
          setFiles((prev) =>
            prev.map((f) =>
              f.id === item.id
                ? {
                    ...f,
                    status: "success",
                    progress: 100,
                    absolute_path: singleFile.absolute_path,
                    parent_source: singleFile.parent_source,
                  }
                : f
            )
          );
        }
      } catch (e) {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === item.id
              ? { ...f, status: "error", progress: 0, error: e instanceof Error ? e.message : "Failed to upload" }
              : f
          )
        );
      }
    }
  }

  // Handler: Remove file from list
  function handleRemoveFile(id: string) {
    setFiles((prev) => {
      const updated = prev.filter((f) => f.id !== id);
      if (updated.length === 0) {
        setSourceData(null);
        setRawQuestions([]);
        setSelectedIndices([]);
      }
      return updated;
    });
  }

  // Handler: Batch Process Ingested Files
  async function handleProcessBatch() {
    const filesToProcess = files
      .filter((f) => f.status === "success" && f.absolute_path)
      .map((f) => ({
        absolute_path: f.absolute_path!,
        parent_source: f.parent_source || null,
        source_file: f.name,
        size_bytes: f.size,
      }));

    if (filesToProcess.length === 0) {
      setError("No files are successfully uploaded and ready to process.");
      return;
    }

    setLoading(true);
    setError("");
    setExtractionProgress("Reading pages and classifying roles...");

    setFiles((prev) =>
      prev.map((f) =>
        f.status === "success" && f.absolute_path ? { ...f, status: "processing" } : f
      )
    );

    try {
      const res = await processSourceBatch(filesToProcess, (msg) => setExtractionProgress(msg));
      setSourceData(res);
      setRawQuestions(res.questions || []);
      
      const allIndices = (res.questions || []).map((_, i) => i);
      setSelectedIndices(allIndices);
      
      setFiles((prev) =>
        prev.map((f) => (f.status === "processing" ? { ...f, status: "success" } : f))
      );
      setExtractionProgress("Extraction complete!");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to process files");
      setFiles((prev) =>
        prev.map((f) => (f.status === "processing" ? { ...f, status: "error", error: "Processing failed" } : f))
      );
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

  // Handler: Execute full mapping & validation pipeline, proceeding to Human Review
  async function proceedToReview() {
    if (!templateId || selectedIndices.length === 0) return;
    setLoading(true);
    setError("");
    setExtractionProgress("Checking schema compatibility...");
    try {
      const activeQuestions = getSelectedQuestions();
      const report = await checkCompatibility(templateId, activeQuestions);
      setCompatibility(report);
      
      setExtractionProgress("Mapping fields & validating answers...");
      const result = await mapQuestions(
        templateId,
        activeQuestions,
        sourceData?.source_filename || files[0]?.name || "source_file",
        sourceData?.source_type || "pdf",
        batchConfig.subject || "General",
        {
          gradeClass: batchConfig.gradeClass,
          chapterTopic: batchConfig.chapterTopic,
          questionType: batchConfig.questionType,
        },
        (msg) => setExtractionProgress(msg)
      );
      setQuestionSetId(result.question_set_id);
      setColumns(result.columns);
      setQuestions(result.questions);
      setCurrentStep("review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Question processing failed");
    } finally {
      setLoading(false);
      setExtractionProgress("");
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

  // Handler: Export (Certified or Draft/Review)
  async function handleExport(format: "csv" | "xlsx", isDraft: boolean = false) {
    if (!questionSetId) return;
    setLoading(true);
    setError("");
    try {
      const blob = await exportQuestionSet(questionSetId, format, isDraft);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const prefix = isDraft ? "draft_review_" : "certified_";
      const safeTitle = (batchConfig.assessmentName || "menntr_assessment").replace(/\s+/g, "_").toLowerCase();
      a.download = `${prefix}${safeTitle}_export.${format}`;
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

      {/* Step 2: Source Files Ingestion & Infill Parsing */}
      {currentStep === "source" && (
        <SourceStep
          files={files}
          sourceData={sourceData}
          loading={loading}
          extractionProgress={extractionProgress}
          onAddFiles={handleAddFiles}
          onRemoveFile={handleRemoveFile}
          onProcessBatch={handleProcessBatch}
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
              proceedToReview();
            }
          }}
        />
      )}

      {/* Step 4: Human Review & AI-Assisted Workspace */}
      {currentStep === "review" && (
        <ReviewStep
          columns={columns}
          questions={questions}
          sourceFilename={sourceData?.source_filename || files[0]?.name || ""}
          batchConfig={batchConfig}
          onCellChange={handleCellChange}
          onQuestionsUpdate={(updatedQuestions) => setQuestions(updatedQuestions)}
          onBack={() => setCurrentStep("selection")}
          onNext={() => setCurrentStep("quality")}
        />
      )}

      {/* Step 5: Quality Dashboard & Quality Gate */}
      {currentStep === "quality" && (
        <QualityDashboardStep
          questions={questions}
          batchConfig={batchConfig}
          onProceedToExport={() => setCurrentStep("export")}
          onJumpToReview={() => setCurrentStep("review")}
          onExportDraft={(format) => handleExport(format, true)}
          onBack={() => setCurrentStep("review")}
        />
      )}

      {/* Step 6: Final Export & Publishing */}
      {currentStep === "export" && (
        <ExportStep
          batchConfig={batchConfig}
          templateName={templateName}
          totalQuestions={questions.length}
          hasValidationErrors={questions.some((q) => !q.validation.valid)}
          loading={loading}
          onExport={(format, isDraft) => handleExport(format, isDraft)}
          onBack={() => setCurrentStep("quality")}
        />
      )}
    </MenntrAppShell>
  );
}
