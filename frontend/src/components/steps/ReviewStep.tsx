"use client";

import React, { useState, useMemo } from "react";
import type {
  QuestionRow,
  AssessmentBatchConfig,
  NormalizedQuestionSuggestion,
  NormalizedFieldSuggestion,
} from "../../types";
import { aiFillMissingFields, aiFillQuestionFields, batchAiFillQuestionFields, updateQuestion } from "../../lib/api";
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
  onQuestionsUpdate?: (updatedQuestions: QuestionRow[]) => void;
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
  onQuestionsUpdate,
  onBack,
  onNext,
}: ReviewStepProps) {
  const [viewMode, setViewMode] = useState<"studio" | "grid">("studio");
  const [showDetails, setShowDetails] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Local mutable copy of questions — initializes from prop, updated by AI fill
  // Individual cell changes still go through onCellChange → parent, but AI fill
  // replaces full question objects locally for instant UI feedback.
  const [localQuestions, setLocalQuestions] = useState<QuestionRow[]>(questions);

  // Keep localQuestions in sync when parent passes new question data
  // (e.g. after a PATCH from onCellChange completes)
  React.useEffect(() => {
    setLocalQuestions(questions);
  }, [questions]);

  // Filters for Grid
  const [searchQuery, setSearchQuery] = useState("");
  const [filterValidation, setFilterValidation] = useState<"all" | "valid" | "invalid">("all");
  const [filterOrigin, setFilterOrigin] = useState<"all" | "extracted" | "inferred" | "user_edited">("all");

  // AI Fill & Bulk Processing States
  const [isAiFilling, setIsAiFilling] = useState(false);
  const [isBatchFilling, setIsBatchFilling] = useState(false);
  const [isProcessingBulk, setIsProcessingBulk] = useState(false);
  const [bulkProgressMessage, setBulkProgressMessage] = useState<string>("");
  const [batchFillProgress, setBatchFillProgress] = useState<string>("");
  const [bulkConfirmationModal, setBulkConfirmationModal] = useState<{
    type: "keep_source" | "apply_ai" | "fill_missing";
    count: number;
    missingFieldsCount?: number;
  } | null>(null);
  const [aiSuggestions, setAiSuggestions] = useState<NormalizedQuestionSuggestion[] | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [aiFillError, setAiFillError] = useState<string>("");
  const [aiSuccessNotice, setAiSuccessNotice] = useState<string>("");

  const filteredQuestions = useMemo(() => {
    return localQuestions.filter((q) => {
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
  }, [localQuestions, searchQuery, filterValidation, filterOrigin]);

  const currentQuestion = localQuestions[currentIndex] || localQuestions[0];

  const findColumnKey = (pattern: RegExp, fallback = "") => {
    return columns.find((c) => pattern.test(c)) || fallback;
  };

  const questionKey = findColumnKey(/question|item_text|prompt/i, columns[0] || "");
  const optAKey = findColumnKey(/option.*a|choice.*a|answer.*1/i, "Option A");
  const optBKey = findColumnKey(/option.*b|choice.*b|answer.*2/i, "Option B");
  const optCKey = findColumnKey(/option.*c|choice.*c|answer.*3/i, "Option C");
  const optDKey = findColumnKey(/option.*d|choice.*d|answer.*4/i, "Option D");

  const findCorrectAnswerColumn = (): string => {
    // 1. Explicit high-priority matches for correct answer
    const explicit = columns.find((c) =>
      /^(?:correct[\s_-]*(?:answer|option|choice)|answer[\s_-]*key|solution)$/i.test(c.trim())
    );
    if (explicit) return explicit;

    // 2. Standalone "Answer" or "Key" (NOT "Answer 1", "Answer A", etc.)
    const standalone = columns.find((c) =>
      /^(?:answer|key|correct)$/i.test(c.trim())
    );
    if (standalone) return standalone;

    // 3. Any column containing "correct" that is NOT an option
    const anyCorrect = columns.find((c) =>
      /correct/i.test(c) && !/(?:option|choice|answer[\s_-]*[1-4a-d])/i.test(c)
    );
    if (anyCorrect) return anyCorrect;

    // 4. Any column containing "answer" that is NOT an option (e.g. not "Answer 1", "answer_1", "answer a")
    const nonOptionAnswer = columns.find((c) =>
      /answer/i.test(c) && !/answer[\s_\-\.]*[1-4a-d]/i.test(c)
    );
    if (nonOptionAnswer) return nonOptionAnswer;

    // 5. Default fallback
    return columns.find((c) => c.toLowerCase() === "correct answer") || "Correct Answer";
  };

  const answerKey = findCorrectAnswerColumn();
  const difficultyKey = findColumnKey(/difficulty|level/i, "Difficulty");
  const topicKey = findColumnKey(/topic|chapter/i, "Topic");
  const bloomsKey = findColumnKey(/bloom/i, "Bloom's Taxonomy");

  // Helper to extract option text from key (A/B/C/D)
  const getOptionText = (key: string) => {
    if (!key || !currentQuestion) return "";
    const k = key.trim().toUpperCase();
    if (k === "A") return currentQuestion.data_json?.[optAKey] || "";
    if (k === "B") return currentQuestion.data_json?.[optBKey] || "";
    if (k === "C") return currentQuestion.data_json?.[optCKey] || "";
    if (k === "D") return currentQuestion.data_json?.[optDKey] || "";
    return "";
  };

  // Helper to resolve an answer key or text into both its canonical key (A-D) and full option text
  const resolveProvenance = (q: QuestionRow | undefined, keyOrText: string | undefined | null) => {
    if (!q || !keyOrText) return { key: "", text: "" };
    const trimmed = String(keyOrText).trim();
    const upper = trimmed.toUpperCase();

    // If letter A, B, C, D
    if (upper === "A" || upper === "B" || upper === "C" || upper === "D") {
      let optText = "";
      if (upper === "A") optText = q.data_json?.[optAKey] || "";
      if (upper === "B") optText = q.data_json?.[optBKey] || "";
      if (upper === "C") optText = q.data_json?.[optCKey] || "";
      if (upper === "D") optText = q.data_json?.[optDKey] || "";
      return { key: upper, text: optText || trimmed };
    }

    // Check if keyOrText matches one of the option texts
    const optA = String(q.data_json?.[optAKey] || "").trim();
    const optB = String(q.data_json?.[optBKey] || "").trim();
    const optC = String(q.data_json?.[optCKey] || "").trim();
    const optD = String(q.data_json?.[optDKey] || "").trim();

    if (optA && optA.toLowerCase() === trimmed.toLowerCase()) return { key: "A", text: optA };
    if (optB && optB.toLowerCase() === trimmed.toLowerCase()) return { key: "B", text: optB };
    if (optC && optC.toLowerCase() === trimmed.toLowerCase()) return { key: "C", text: optC };
    if (optD && optD.toLowerCase() === trimmed.toLowerCase()) return { key: "D", text: optD };

    return { key: "", text: trimmed };
  };

  // Distinct Answer Provenance & Decision State
  const rawSourceAns = (
    currentQuestion?.source_answer_text ||
    currentQuestion?.source_answer ||
    currentQuestion?.source_metadata?.answer_source ||
    ""
  ).trim();

  const rawAiAns = (
    currentQuestion?.ai_answer_text ||
    currentQuestion?.ai_answer ||
    currentQuestion?.validation?.ai_validation?.ai_answer ||
    ""
  ).trim();

  const sourceProv = resolveProvenance(currentQuestion, rawSourceAns);
  const sourceKey = sourceProv.key || (currentQuestion?.source_answer_key || "").trim().toUpperCase();
  const sourceText = sourceProv.text || currentQuestion?.source_answer_text || getOptionText(sourceKey) || rawSourceAns;
  const sourceAnswerVal = sourceText || sourceKey;

  const aiProv = resolveProvenance(currentQuestion, rawAiAns);
  const aiKey = aiProv.key || (currentQuestion?.ai_answer_key || "").trim().toUpperCase();
  const aiText = aiProv.text || currentQuestion?.ai_answer_text || getOptionText(aiKey) || rawAiAns;
  const aiAnswerVal = aiText || aiKey;

  const rawFinalAns = (
    currentQuestion?.final_answer_text ||
    currentQuestion?.final_answer ||
    currentQuestion?.data_json?.[answerKey] ||
    sourceText ||
    aiText ||
    ""
  ).trim();

  const finalProv = resolveProvenance(currentQuestion, rawFinalAns);
  const finalKey = finalProv.key || (currentQuestion?.final_answer_key || "").trim().toUpperCase();
  const finalText = finalProv.text || currentQuestion?.final_answer_text || getOptionText(finalKey) || rawFinalAns;
  const finalAnswerVal = finalText;

  const aiConfidenceVal =
    typeof currentQuestion?.validation?.ai_validation?.confidence === "number"
      ? currentQuestion.validation.ai_validation.confidence
      : 0.98;

  const isAnswerConflict = Boolean(
    sourceKey &&
    aiKey &&
    sourceKey !== aiKey
  );

  const isMissingSource = !sourceAnswerVal && !sourceKey;

  const isMatchesSource = Boolean(
    sourceKey &&
    aiKey &&
    sourceKey === aiKey
  );

  const duplicateOptionsMessage = useMemo(() => {
    if (!currentQuestion) return null;
    const optValues = [
      { key: "A", val: (currentQuestion.data_json?.[optAKey] || "").trim() },
      { key: "B", val: (currentQuestion.data_json?.[optBKey] || "").trim() },
      { key: "C", val: (currentQuestion.data_json?.[optCKey] || "").trim() },
      { key: "D", val: (currentQuestion.data_json?.[optDKey] || "").trim() },
    ].filter(o => o.val !== "");

    const seen = new Map<string, string>();
    for (const opt of optValues) {
      if (seen.has(opt.val)) {
        return `Options ${seen.get(opt.val)} and ${opt.key} contain the same value.`;
      }
      seen.set(opt.val, opt.key);
    }
    return null;
  }, [currentQuestion, optAKey, optBKey, optCKey, optDKey]);

  const validationStatus = currentQuestion?.validation?.ai_validation?.validation_status || currentQuestion?.status || "";
  const isConflict = isAnswerConflict;
  const isMissing = isMissingSource || validationStatus === "MISSING_ANSWER" || !sourceKey;
  const isAmbiguity = validationStatus === "AMBIGUOUS" || !!duplicateOptionsMessage;

  // Available options for Final Answer select dropdown
  const availableOptionChoices = useMemo(() => {
    if (!currentQuestion) return [];
    const choices: { value: string; label: string }[] = [];

    const letters = [
      { key: optAKey, letter: "A" },
      { key: optBKey, letter: "B" },
      { key: optCKey, letter: "C" },
      { key: optDKey, letter: "D" },
    ];

    letters.forEach(({ key, letter }) => {
      const optVal = (currentQuestion.data_json?.[key] || "").trim();
      if (optVal) {
        choices.push({
          value: letter,
          label: `${letter}: ${optVal.length > 40 ? optVal.slice(0, 40) + "..." : optVal}`,
        });
      } else {
        choices.push({ value: letter, label: `Option ${letter}` });
      }
    });

    if (sourceAnswerVal && !["A", "B", "C", "D"].includes(sourceAnswerVal.toUpperCase())) {
      if (!choices.some((c) => c.value.toLowerCase() === sourceAnswerVal.toLowerCase())) {
        choices.push({ value: sourceAnswerVal, label: `Source: ${sourceAnswerVal}` });
      }
    }

    if (aiAnswerVal && !["A", "B", "C", "D"].includes(aiAnswerVal.toUpperCase())) {
      if (!choices.some((c) => c.value.toLowerCase() === aiAnswerVal.toLowerCase())) {
        choices.push({ value: aiAnswerVal, label: `AI: ${aiAnswerVal}` });
      }
    }

    if (
      finalAnswerVal &&
      !choices.some((c) => c.value.toLowerCase() === finalAnswerVal.toLowerCase())
    ) {
      choices.push({ value: finalAnswerVal, label: `Custom: ${finalAnswerVal}` });
    }

    return choices;
  }, [currentQuestion, optAKey, optBKey, optCKey, optDKey, sourceAnswerVal, aiAnswerVal, finalAnswerVal]);

  // Helper to extract Source Key from any QuestionRow
  const getQuestionSourceKey = (q: QuestionRow | undefined) => {
    if (!q) return "";
    const srcVal = (
      q.source_answer ||
      q.source_metadata?.answer_source ||
      ""
    ).trim();
    return (q.source_answer_key || srcVal || "").trim().toUpperCase();
  };

  // Helper to extract AI Key from any QuestionRow
  const getQuestionAiKey = (q: QuestionRow | undefined) => {
    if (!q) return "";
    const aiVal = (
      q.ai_answer ||
      q.validation?.ai_validation?.ai_answer ||
      ""
    ).trim();
    return (q.ai_answer_key || aiVal || "").trim().toUpperCase();
  };

  // Helper to determine if a value is missing or empty
  const isFieldMissing = (val: unknown) => {
    if (val === null || val === undefined) return true;
    const str = String(val).trim();
    return str === "" || str === "null" || str === "undefined";
  };

  // Helper to identify core question/option/answer columns (which are not metadata)
  const isCoreQuestionColumn = (col: string) => {
    const coreFields = new Set([questionKey, optAKey, optBKey, optCKey, optDKey, answerKey]);
    if (coreFields.has(col)) return true;
    const answerKeywords = ["answer", "correct", "solution", "key"];
    if (answerKeywords.some((kw) => col.toLowerCase().includes(kw))) return true;
    if (/question|item_text|prompt/i.test(col)) return true;
    if (/option|choice/i.test(col)) return true;
    return false;
  };

  // Total missing metadata fields across the entire assessment
  const totalMissingFieldsCount = useMemo(() => {
    let total = 0;
    localQuestions.forEach((q) => {
      columns.forEach((col) => {
        if (!isCoreQuestionColumn(col) && isFieldMissing(q.data_json?.[col])) {
          total += 1;
        }
      });
    });
    return total;
  }, [localQuestions, columns, questionKey, optAKey, optBKey, optCKey, optDKey, answerKey]);

  // Applicable questions for bulk operations
  const applicableSourceQuestions = useMemo(() => {
    return localQuestions.filter((q) => {
      const srcKey = getQuestionSourceKey(q);
      return Boolean(srcKey);
    });
  }, [localQuestions]);

  const applicableAiQuestions = useMemo(() => {
    return localQuestions.filter((q) => {
      const aiKey = getQuestionAiKey(q);
      return Boolean(aiKey);
    });
  }, [localQuestions]);

  const handleSetQuestionFinalAnswer = (q: QuestionRow, newAnswer: string) => {
    if (!q || !newAnswer) return;
    const { key, text } = resolveProvenance(q, newAnswer);
    const resolvedText = text || newAnswer;
    q.final_answer = resolvedText;
    q.final_answer_text = resolvedText;
    q.final_answer_key = key || q.final_answer_key;
    onCellChange(q.id, answerKey, resolvedText);
  };

  const handleSetFinalAnswer = (newAnswer: string) => {
    if (!currentQuestion) return;
    handleSetQuestionFinalAnswer(currentQuestion, newAnswer);
  };

  // Robust, sequential, persistent bulk answer update handler
  const executeBulkAnswerAction = async (type: "source" | "ai") => {
    if (isProcessingBulk || isBatchFilling || isAiFilling) return;
    setIsProcessingBulk(true);
    setBulkConfirmationModal(null);
    setAiFillError("");
    setAiSuccessNotice("");

    const targetQuestions = type === "source" ? applicableSourceQuestions : applicableAiQuestions;
    const total = targetQuestions.length;
    let updatedCount = 0;
    let failedCount = 0;
    const failedReasons: string[] = [];

    const updatedList = [...localQuestions];

    for (let i = 0; i < total; i++) {
      const q = targetQuestions[i];
      const rawAns = type === "source"
        ? (q.source_answer_text || q.source_answer || getQuestionSourceKey(q))
        : (q.ai_answer_text || q.ai_answer || getQuestionAiKey(q));

      const { key, text } = resolveProvenance(q, rawAns);
      const targetAns = text || rawAns;

      setBulkProgressMessage(
        `Processing question ${i + 1} of ${total}: ${type === "source" ? "Preserving source answer" : "Applying AI suggestion"} (${targetAns})...`
      );

      if (!targetAns) {
        failedCount += 1;
        continue;
      }

      try {
        const persistedQ = await updateQuestion(q.id, { [answerKey]: targetAns });
        const idxInList = updatedList.findIndex((item) => item.id === q.id);
        if (idxInList !== -1) {
          updatedList[idxInList] = {
            ...persistedQ,
            final_answer: targetAns,
            final_answer_text: targetAns,
            final_answer_key: key,
          };
        }
        updatedCount += 1;
      } catch (err: any) {
        failedCount += 1;
        failedReasons.push(err?.message || `Question #${q.row_number || i + 1} failed`);
        const idxInList = updatedList.findIndex((item) => item.id === q.id);
        const fallbackQ: QuestionRow = {
          ...q,
          final_answer: targetAns,
          final_answer_key: key,
          final_answer_text: targetAns,
          data_json: { ...(q.data_json || {}), [answerKey]: targetAns },
        };
        if (idxInList !== -1) {
          updatedList[idxInList] = fallbackQ;
        }
        onCellChange(q.id, answerKey, targetAns);
      }
    }

    setLocalQuestions(updatedList);
    onQuestionsUpdate?.(updatedList);
    setIsProcessingBulk(false);
    setBulkProgressMessage("");

    if (failedCount === 0) {
      if (type === "source") {
        setAiSuccessNotice(`✓ Source answers preserved: ${updatedCount} of ${total} questions now use their original source answers.`);
      } else {
        setAiSuccessNotice(`✓ AI suggestions applied: ${updatedCount} of ${total} questions updated.`);
      }
    } else {
      const failDetail = failedReasons.length > 0 ? ` (${failedReasons.join("; ")})` : "";
      setAiSuccessNotice(
        `Completed: ${updatedCount} of ${total} questions updated. ${failedCount} question${failedCount === 1 ? "" : "s"} could not be saved${failDetail}.`
      );
    }
  };

  const handleApproveAndNext = () => {
    if (!currentQuestion) return;
    const ans = finalAnswerVal || sourceAnswerVal || aiAnswerVal || "A";
    handleSetFinalAnswer(ans);
    if (currentIndex < localQuestions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      onNext();
    }
  };

  // Identify missing metadata fields for current question
  const currentMissingFields = useMemo(() => {
    if (!currentQuestion) return [];
    const missing: string[] = [];
    columns.forEach((col) => {
      if (!isCoreQuestionColumn(col) && isFieldMissing(currentQuestion.data_json?.[col])) {
        missing.push(col);
      }
    });
    return missing;
  }, [currentQuestion, columns]);

  // Suggestions specifically for current question
  const currentQuestionSuggestions = useMemo(() => {
    if (!currentQuestion || !aiSuggestions) return null;
    return aiSuggestions.find((s) => s.questionId === currentQuestion.id) || null;
  }, [currentQuestion, aiSuggestions]);

  // ──────────────────────────────────────────────────────────────────────────────
  // ONE-CLICK AI Fill for the current question
  // The backend determines all missing fields, makes ONE focused AI call,
  // atomically persists all resolved fields, and returns the complete updated question.
  // ──────────────────────────────────────────────────────────────────────────────
  const handleTriggerAIFillForCurrent = async () => {
    if (!currentQuestion) return;
    // Guard against duplicate simultaneous requests
    if (isAiFilling || isBatchFilling) return;

    setIsAiFilling(true);
    setAiFillError("");
    setAiSuccessNotice("");

    try {
      // Single API call — backend resolves ALL missing fields atomically
      const updatedQuestion = await aiFillQuestionFields(currentQuestion.id, {
        subject: batchConfig.subject || "General",
        gradeClass: batchConfig.gradeClass || "General",
        chapterTopic: batchConfig.chapterTopic || "General",
        questionType: batchConfig.questionType || "Multiple Choice (MCQ)",
      });

      // Replace question in state with the complete updated object from backend
      setLocalQuestions((prev) =>
        prev.map((q) => (q.id === updatedQuestion.id ? updatedQuestion : q))
      );
      // Notify parent so other steps (Quality Dashboard, Export) see the update
      onQuestionsUpdate?.([...localQuestions.map((q) =>
        q.id === updatedQuestion.id ? updatedQuestion : q
      )]);

      // Construct pending AI suggestions for fields that require review (under confidence threshold)
      const pendingFields: Record<string, NormalizedFieldSuggestion> = {};
      Object.entries(updatedQuestion.source_metadata?.fields || {}).forEach(([fname, fval]: [string, any]) => {
        if (fval.review_required && fval.ai_suggestion) {
          pendingFields[fname] = {
            fieldName: fname,
            value: fval.ai_suggestion,
            status: "AI_INFERRED",
            confidence: fval.confidence,
            reason: fval.reason,
            isEditing: false,
            editValue: fval.ai_suggestion,
          };
        }
      });

      if (Object.keys(pendingFields).length > 0) {
        const suggestionObj: NormalizedQuestionSuggestion = {
          questionId: updatedQuestion.id,
          rowNumber: updatedQuestion.row_number || 1,
          questionPrompt: updatedQuestion.data_json?.[questionKey] || `Question #${updatedQuestion.row_number}`,
          fields: pendingFields,
        };
        setAiSuggestions((prev) => {
          const list = prev ? prev.filter((s) => s.questionId !== updatedQuestion.id) : [];
          return [...list, suggestionObj];
        });
      } else {
        setAiSuggestions((prev) => prev ? prev.filter((s) => s.questionId !== updatedQuestion.id) : null);
      }

      const res = updatedQuestion.ai_fill_result;
      const resCount = res?.resolved_count ?? 0;
      const unresCount = (res?.review_required_count ?? 0) + (res?.unresolved_count ?? 0);

      if (res?.status === "already_complete" || (resCount === 0 && unresCount === 0 && currentMissingFields.length === 0)) {
        setAiSuccessNotice("All schema metadata fields are already populated.");
      } else if (unresCount === 0 && resCount > 0) {
        setAiSuccessNotice(`✓ ${resCount} field${resCount === 1 ? "" : "s"} filled • 0 fields remaining`);
      } else if (resCount > 0 && unresCount > 0) {
        setAiSuccessNotice(`✓ ${resCount} field${resCount === 1 ? "" : "s"} filled • ${unresCount} field${unresCount === 1 ? "" : "s"} require review`);
      } else if (resCount === 0 && unresCount > 0) {
        setAiSuccessNotice(`0 fields filled • ${unresCount} field${unresCount === 1 ? "" : "s"} require review`);
      } else {
        setAiSuccessNotice("AI inference completed.");
      }
    } catch (e) {
      let safeMsg = "AI field inference failed. Please try again.";
      if (e instanceof Error && e.message) {
        const clean = e.message
          .replace(/https?:\/\/[^\s]+/g, "")
          .replace(/[a-zA-Z0-9]{32,}/g, "***");
        if (clean.length < 200) safeMsg = clean;
      }
      setAiFillError(safeMsg);
    } finally {
      setIsAiFilling(false);
    }
  };

  // ──────────────────────────────────────────────────────────────────────────────
  // BATCH AI Fill — resolves missing fields for all questions in one atomic operation
  // ──────────────────────────────────────────────────────────────────────────────
  const handleTriggerBatchAIFill = async () => {
    if (localQuestions.length === 0) return;
    if (isAiFilling || isBatchFilling || isProcessingBulk) return;

    setIsBatchFilling(true);
    setIsProcessingBulk(true);
    setAiFillError("");
    setAiSuccessNotice("");
    setBatchFillProgress("Running bulk AI fill for all questions...");

    const context = {
      subject: batchConfig.subject || "General",
      gradeClass: batchConfig.gradeClass || "General",
      chapterTopic: batchConfig.chapterTopic || "General",
      questionType: batchConfig.questionType || "Multiple Choice (MCQ)",
    };

    try {
      const batchRes = await batchAiFillQuestionFields(localQuestions.map((q) => q.id), context);
      const { summary, questions: updatedQuestions } = batchRes;

      // Apply all updates at once
      setLocalQuestions(updatedQuestions);
      onQuestionsUpdate?.(updatedQuestions);

      // Collect all pending suggestions from the updated questions
      const allPendingSuggestions: NormalizedQuestionSuggestion[] = [];
      updatedQuestions.forEach((uq) => {
        const pendingFields: Record<string, NormalizedFieldSuggestion> = {};
        Object.entries(uq.source_metadata?.fields || {}).forEach(([fname, fval]: [string, any]) => {
          if (fval.review_required && fval.ai_suggestion) {
            pendingFields[fname] = {
              fieldName: fname,
              value: fval.ai_suggestion,
              status: "AI_INFERRED",
              confidence: fval.confidence,
              reason: fval.reason,
              isEditing: false,
              editValue: fval.ai_suggestion,
            };
          }
        });
        if (Object.keys(pendingFields).length > 0) {
          allPendingSuggestions.push({
            questionId: uq.id,
            rowNumber: uq.row_number || 1,
            questionPrompt: uq.data_json?.[questionKey] || `Question #${uq.row_number}`,
            fields: pendingFields,
          });
        }
      });

      setAiSuggestions(allPendingSuggestions.length > 0 ? allPendingSuggestions : null);

      setAiSuccessNotice(
        `AI Fill Complete • Questions processed: ${summary.questions_processed} • Fields filled: ${summary.fields_filled} • Already populated: ${summary.already_populated} • Needs review: ${summary.needs_review} • Failed: ${summary.failed}`
      );
    } catch (err: any) {
      setAiFillError(err?.message || "Bulk AI fill failed. Please try again.");
    } finally {
      setBatchFillProgress("");
      setIsBatchFilling(false);
      setIsProcessingBulk(false);
    }
  };

  // Guard for batch fill: open confirmation modal before processing
  const handleTriggerBatchAIFillGuarded = () => {
    if (localQuestions.length === 0 || isProcessingBulk || isBatchFilling || isAiFilling) return;
    setBulkConfirmationModal({
      type: "fill_missing",
      count: localQuestions.length,
      missingFieldsCount: totalMissingFieldsCount,
    });
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
            <ReviewIcon size={22} color="var(--primary-hover)" /> Step 4: Human Review
          </div>
          <div className="card-subtitle">
            Authoritative human review workspace. Verify answer parity and leverage AI to infill missing metadata.
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

      {/* Active Bulk Processing Status Banner */}
      {(isProcessingBulk || isBatchFilling) && (
        <div
          style={{
            background: "rgba(37, 99, 235, 0.15)",
            border: "1px solid rgba(59, 130, 246, 0.4)",
            borderRadius: "10px",
            padding: "14px 18px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "14px",
          }}
        >
          <div
            style={{
              width: "20px",
              height: "20px",
              border: "3px solid rgba(59, 130, 246, 0.3)",
              borderTopColor: "#3B82F6",
              borderRadius: "50%",
              animation: "spin 1s linear infinite",
            }}
          />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: "0.88rem", color: "#FFFFFF", marginBottom: "3px" }}>
              {isBatchFilling ? "AI INFERENCE IN PROGRESS" : "BULK PERSISTENCE IN PROGRESS"}
            </div>
            <div style={{ fontSize: "0.80rem", color: "#93C5FD" }}>
              {bulkProgressMessage || batchFillProgress || "Processing questions sequentially and persisting to database..."}
            </div>
          </div>
        </div>
      )}

      {/* STUDIO MODE (Source vs Extracted vs AI Assist vs Final) */}
      {viewMode === "studio" && currentQuestion && (
        <div>
          {/* Compact Question Navigator */}
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "10px",
              padding: "12px 16px",
              marginBottom: "16px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
              <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "8px" }}>
                <span>Questions Navigator</span>
                <span style={{ fontSize: "0.74rem", fontWeight: 500, color: "var(--text-muted)" }}>
                  ({localQuestions.length} total • Question {currentIndex + 1} selected)
                </span>
              </div>
              <div style={{ display: "flex", gap: "12px", fontSize: "0.72rem", color: "var(--text-muted)", flexWrap: "wrap" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--accent)" }} /> Valid
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--danger)" }} /> Conflict / Issue
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--warning)" }} /> Missing Fields
                </span>
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(64px, 1fr))",
                gap: "6px",
                maxHeight: "130px",
                overflowY: "auto",
                padding: "2px",
              }}
            >
              {localQuestions.map((q, idx) => {
                const isSelected = idx === currentIndex;
                const isValid = q.validation?.valid;
                const hasConflict = Boolean(
                  q.source_answer && q.ai_answer && q.source_answer.toUpperCase() !== q.ai_answer.toUpperCase()
                );
                const isMissingAnswer = !q.source_answer && !q.final_answer;
                const hasMissingFields = columns.some((col) => {
                  const isCore = [questionKey, optAKey, optBKey, optCKey, optDKey, answerKey].includes(col);
                  return !isCore && !/answer|correct/i.test(col) && !String(q.data_json?.[col] || "").trim();
                });

                let statusColor = "var(--accent)";
                let statusSymbol = "✓";
                if (hasConflict || !isValid) {
                  statusColor = "var(--danger)";
                  statusSymbol = "!";
                } else if (isMissingAnswer) {
                  statusColor = "var(--warning)";
                  statusSymbol = "?";
                } else if (hasMissingFields) {
                  statusColor = "var(--warning)";
                  statusSymbol = "•";
                }

                return (
                  <button
                    key={q.id || idx}
                    type="button"
                    onClick={() => setCurrentIndex(idx)}
                    style={{
                      padding: "6px 4px",
                      fontSize: "0.78rem",
                      fontWeight: isSelected ? 800 : 600,
                      borderRadius: "6px",
                      border: isSelected
                        ? "2px solid var(--primary-hover)"
                        : "1px solid var(--border-subtle)",
                      background: isSelected
                        ? "rgba(124, 58, 237, 0.2)"
                        : "rgba(0, 0, 0, 0.2)",
                      color: isSelected ? "#FFFFFF" : "var(--text-primary)",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "2px",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                      <span>{String(idx + 1).padStart(2, "0")}</span>
                      <span style={{ fontSize: "0.68rem", color: statusColor, fontWeight: 800 }}>
                        {statusSymbol}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

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
                Question {currentIndex + 1} of {localQuestions.length}
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
              {/* Prominent Global AI Fill Action — fills ALL questions */}
              <button
                className="accent"
                onClick={handleTriggerBatchAIFillGuarded}
                disabled={isAiFilling || isBatchFilling || isProcessingBulk}
                style={{ padding: "6px 14px", fontSize: "0.82rem", gap: "6px" }}
              >
                <SparklesIcon size={15} />
                {isBatchFilling
                  ? (batchFillProgress || "Filling All Questions...")
                  : isAiFilling
                  ? "Filling..."
                  : "✨ Fill All Missing Fields with AI"}
              </button>

              <div style={{ display: "flex", gap: "6px" }}>
                <button
                  className="secondary"
                  onClick={() => setShowDetails(!showDetails)}
                  style={{ padding: "6px 12px", fontSize: "0.8rem", gap: "4px" }}
                >
                  {showDetails ? "Hide AI Details" : "View AI Details"}
                </button>
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
                  disabled={currentIndex === localQuestions.length - 1}
                  onClick={() => setCurrentIndex((prev) => Math.min(localQuestions.length - 1, prev + 1))}
                  style={{ padding: "6px 12px", fontSize: "0.8rem", gap: "4px" }}
                >
                  Next <ArrowRightIcon size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Split Container */}
          <div
            className="review-studio-container"
            style={{
              gridTemplateColumns: showDetails ? "340px 1fr" : "1fr",
              maxWidth: showDetails ? "100%" : "800px",
              margin: "0 auto",
            }}
          >
            {/* Left Column: SOURCE CONTEXT & AI INFILL HUB */}
            {showDetails && (
              <div className="studio-source-panel">
              {/* Cross-Page Traceability & Source Context */}
              <div style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", gap: "6px" }}>
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
                      onClick={handleTriggerAIFillForCurrent}
                      disabled={isAiFilling || isBatchFilling}
                      style={{ width: "100%", padding: "8px 12px", fontSize: "0.82rem", gap: "6px" }}
                    >
                      <SparklesIcon size={14} />
                      {isAiFilling
                        ? "✨ Filling Missing Fields..."
                        : "✨ Fill Missing Fields with AI"}
                    </button>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "6px", lineHeight: "1.4" }}>
                      AI will infer ALL eligible missing fields in one operation and update this question immediately.
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
                          {origin === "inferred" ? `AI_INFERRED · ${(confidence * 100).toFixed(0)}%` : origin === "user_edited" ? "Edited" : "Source"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            )}

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

              {/* ANSWER VALIDATION & DECISION SECTION */}
              <div
                style={{
                  background: "var(--bg-surface)",
                  border: isConflict ? "1px solid rgba(239, 68, 68, 0.4)" : "1px solid var(--border-medium)",
                  borderRadius: "12px",
                  padding: "16px",
                  marginTop: "6px",
                  marginBottom: "6px",
                }}
              >
                {/* Bulk Answer Decision Cards */}
                <div
                  style={{
                    background: "rgba(15, 23, 42, 0.7)",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "12px",
                    padding: "16px",
                    marginBottom: "16px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <SparklesIcon size={18} color="#93C5FD" />
                      <span style={{ fontSize: "0.88rem", fontWeight: 700, color: "var(--text-primary)" }}>
                        Bulk Answer Decisions ({localQuestions.length} Total Questions)
                      </span>
                    </div>
                    <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
                      Affects all applicable questions across the current assessment
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
                    {/* Card 1: Keep Source Answers for All */}
                    <div
                      style={{
                        background: "rgba(255, 255, 255, 0.04)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "8px",
                        padding: "14px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        gap: "10px",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                          <strong style={{ fontSize: "0.85rem", color: "#F8FAFC" }}>Keep Source Answers for All</strong>
                          <span className="badge info" style={{ fontSize: "0.7rem", padding: "2px 6px" }}>
                            {applicableSourceQuestions.length} applicable
                          </span>
                        </div>
                        <p style={{ margin: 0, fontSize: "0.76rem", color: "var(--text-secondary)", lineHeight: "1.35" }}>
                          Use the extracted source answer for every question. AI suggestions will not replace source answers.
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={applicableSourceQuestions.length === 0 || isProcessingBulk || isBatchFilling}
                        onClick={() => setBulkConfirmationModal({ type: "keep_source", count: applicableSourceQuestions.length })}
                        style={{
                          padding: "8px 14px",
                          fontSize: "0.80rem",
                          fontWeight: 600,
                          background: "rgba(255, 255, 255, 0.08)",
                          border: "1px solid rgba(255, 255, 255, 0.25)",
                          color: "#F8FAFC",
                          borderRadius: "6px",
                          cursor: (applicableSourceQuestions.length === 0 || isProcessingBulk || isBatchFilling) ? "not-allowed" : "pointer",
                          opacity: (applicableSourceQuestions.length === 0 || isProcessingBulk || isBatchFilling) ? 0.45 : 1,
                          width: "100%",
                          justifyContent: "center",
                        }}
                      >
                        Keep Source Answers for All
                      </button>
                    </div>

                    {/* Card 2: Apply AI Suggestions to All */}
                    <div
                      style={{
                        background: "rgba(5, 150, 105, 0.08)",
                        border: "1px solid rgba(16, 185, 129, 0.25)",
                        borderRadius: "8px",
                        padding: "14px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        gap: "10px",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                          <strong style={{ fontSize: "0.85rem", color: "#34D399" }}>Apply AI Suggestions to All</strong>
                          <span className="badge success" style={{ fontSize: "0.7rem", padding: "2px 6px" }}>
                            {applicableAiQuestions.length} applicable
                          </span>
                        </div>
                        <p style={{ margin: 0, fontSize: "0.76rem", color: "var(--text-secondary)", lineHeight: "1.35" }}>
                          Apply the reviewed AI answer suggestions across all questions.
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={applicableAiQuestions.length === 0 || isProcessingBulk || isBatchFilling}
                        onClick={() => setBulkConfirmationModal({ type: "apply_ai", count: applicableAiQuestions.length })}
                        style={{
                          padding: "8px 14px",
                          fontSize: "0.80rem",
                          fontWeight: 600,
                          background: "#059669",
                          border: "1px solid #10B981",
                          color: "#FFFFFF",
                          borderRadius: "6px",
                          boxShadow: "0 2px 6px rgba(16, 185, 129, 0.25)",
                          cursor: (applicableAiQuestions.length === 0 || isProcessingBulk || isBatchFilling) ? "not-allowed" : "pointer",
                          opacity: (applicableAiQuestions.length === 0 || isProcessingBulk || isBatchFilling) ? 0.45 : 1,
                          width: "100%",
                          justifyContent: "center",
                        }}
                      >
                        Apply AI Suggestions to All
                      </button>
                    </div>
                  </div>
                </div>

                {/* Simplified Status View */}
                {isConflict ? (
                  <div style={{ background: "rgba(239, 68, 68, 0.05)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: "8px", padding: "14px", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--danger)", fontWeight: 700, fontSize: "1rem", marginBottom: "6px" }}>
                      <AlertTriangleIcon size={16} /> Answer Conflict
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                      The AI answer does not match the source answer.
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "12px" }}>
                      <div style={{ background: "rgba(0,0,0,0.15)", padding: "8px", borderRadius: "6px" }}>
                        <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Source Answer</div>
                        <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                          {sourceKey ? `${sourceKey} → ${sourceText}` : "Missing"}
                        </div>
                      </div>
                      <div style={{ background: "rgba(0,0,0,0.15)", padding: "8px", borderRadius: "6px" }}>
                        <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", textTransform: "uppercase" }}>AI Verification</div>
                        <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--primary-hover)" }}>
                          {aiKey ? `${aiKey} → ${aiText}` : "None"}
                        </div>
                      </div>
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                      Confidence: <strong>{(aiConfidenceVal * 100).toFixed(0)}%</strong>
                    </div>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => handleSetFinalAnswer(sourceKey)}
                        style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 600 }}
                      >
                        Keep Source Answer ({sourceKey})
                      </button>
                      <button
                        type="button"
                        className="accent"
                        onClick={() => handleSetFinalAnswer(aiKey)}
                        style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 600 }}
                      >
                        Use AI Suggestion ({aiKey})
                      </button>
                    </div>
                  </div>
                ) : isMissing ? (
                  <div style={{ background: "rgba(245, 158, 11, 0.05)", border: "1px solid rgba(245, 158, 11, 0.25)", borderRadius: "8px", padding: "14px", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--warning)", fontWeight: 700, fontSize: "1rem", marginBottom: "6px" }}>
                      <SparklesIcon size={16} /> Missing Answer
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                      No correct answer was found in the source document. AI has suggested an answer.
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "12px" }}>
                      <div style={{ background: "rgba(0,0,0,0.15)", padding: "8px", borderRadius: "6px" }}>
                        <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Source Answer</div>
                        <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--danger)" }}>Missing</div>
                      </div>
                      <div style={{ background: "rgba(0,0,0,0.15)", padding: "8px", borderRadius: "6px" }}>
                        <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", textTransform: "uppercase" }}>AI Verification</div>
                        <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--primary-hover)" }}>
                          {aiKey ? `${aiKey} → ${aiText}` : "None"}
                        </div>
                      </div>
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                      Confidence: <strong>{(aiConfidenceVal * 100).toFixed(0)}%</strong>
                    </div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        type="button"
                        className="accent"
                        onClick={() => handleSetFinalAnswer(aiKey)}
                        style={{ padding: "6px 12px", fontSize: "0.8rem", fontWeight: 600 }}
                      >
                        Use AI Suggestion ({aiKey})
                      </button>
                    </div>
                  </div>
                ) : isAmbiguity ? (
                  <div style={{ background: "rgba(245, 158, 11, 0.05)", border: "1px solid rgba(245, 158, 11, 0.25)", borderRadius: "8px", padding: "14px", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--warning)", fontWeight: 700, fontSize: "1rem", marginBottom: "6px" }}>
                      <AlertTriangleIcon size={16} /> Ambiguous Answer
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "6px" }}>
                      {duplicateOptionsMessage || "Two options contain the same answer value or the option mapping is ambiguous."}
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      Confidence: <strong>{(aiConfidenceVal * 100).toFixed(0)}%</strong>
                    </div>
                  </div>
                ) : (
                  <div style={{ background: "rgba(16, 185, 129, 0.05)", border: "1px solid rgba(16, 185, 129, 0.25)", borderRadius: "8px", padding: "14px", marginBottom: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--accent)", fontWeight: 700, fontSize: "1rem", marginBottom: "6px" }}>
                      <CheckCircleIcon size={16} /> Answer Verified
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "6px" }}>
                      Source Answer: <strong>{sourceKey ? `${sourceKey} → ${sourceText}` : "None"}</strong> | AI Verification: <strong>{aiKey ? `${aiKey} → ${aiText}` : "None"}</strong>
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                      Confidence: <strong>{(aiConfidenceVal * 100).toFixed(0)}%</strong>
                    </div>
                  </div>
                )}

                {/* Final Decision Input row */}
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "12px", borderTop: "1px solid var(--border-subtle)", paddingTop: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-secondary)" }}>
                      Final Selection:
                    </span>
                    <select
                      value={finalKey}
                      onChange={(e) => handleSetFinalAnswer(e.target.value)}
                      style={{ padding: "6px 10px", fontSize: "0.84rem", fontWeight: 700, borderRadius: "6px", border: "1px solid var(--border-medium)", background: "var(--bg-surface)", minWidth: "160px" }}
                    >
                      <option value="">— Select Option —</option>
                      {availableOptionChoices.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    
                    <input
                      type="text"
                      value={finalAnswerVal}
                      onChange={(e) => handleSetFinalAnswer(e.target.value)}
                      placeholder="Or type custom final answer..."
                      style={{ padding: "6px 10px", fontSize: "0.82rem", borderRadius: "6px", border: "1px solid var(--border-medium)", flex: 1, background: "var(--bg-surface)" }}
                    />
                  </div>

                  <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                    {["A", "B", "C", "D"].map((letter) => {
                      const isSelected = finalKey === letter;
                      return (
                        <button
                          key={letter}
                          type="button"
                          className={isSelected ? "primary" : "secondary"}
                          onClick={() => handleSetFinalAnswer(letter)}
                          style={{ padding: "4px 10px", fontSize: "0.74rem", flex: 1, justifyContent: "center" }}
                        >
                          {letter}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Difficulty & Additional Schema Metadata Fields */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px", marginTop: "4px" }}>
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

                {columns
                  .filter((c) => ![questionKey, optAKey, optBKey, optCKey, optDKey, answerKey, difficultyKey].includes(c) && !/answer|correct/i.test(c))
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
                  onClick={handleApproveAndNext}
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
              onClick={() => handleTriggerBatchAIFill()}
              disabled={isAiFilling || isBatchFilling}
              style={{ padding: "10px 16px", fontSize: "0.85rem", gap: "6px" }}
            >
              <SparklesIcon size={16} /> {(isAiFilling || isBatchFilling) ? "Inferring Missing Fields..." : "✨ Fill Missing Fields with AI"}
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

      {/* Generic Bulk Action Confirmation Modal */}
      {bulkConfirmationModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 110,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-card-solid)",
              border: "1px solid var(--border-medium)",
              borderRadius: "16px",
              padding: "24px",
              maxWidth: "520px",
              width: "100%",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
              <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 800, color: "var(--text-primary)" }}>
                {bulkConfirmationModal.type === "keep_source"
                  ? "KEEP SOURCE ANSWERS FOR ALL?"
                  : bulkConfirmationModal.type === "apply_ai"
                  ? "APPLY AI SUGGESTIONS TO ALL?"
                  : "FILL ALL MISSING FIELDS WITH AI"}
              </h3>
              <button
                className="secondary"
                onClick={() => setBulkConfirmationModal(null)}
                style={{ padding: "4px 8px" }}
              >
                <XIcon size={16} />
              </button>
            </div>

            <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.5", marginBottom: "16px" }}>
              {bulkConfirmationModal.type === "keep_source" && (
                <div>
                  <p style={{ marginTop: 0 }}>
                    This will keep the original source answer for every question in this assessment.
                  </p>
                  <div style={{ background: "rgba(0,0,0,0.25)", padding: "10px 14px", borderRadius: "8px", margin: "10px 0" }}>
                    <div><strong>Questions affected:</strong> {bulkConfirmationModal.count} of {localQuestions.length}</div>
                    <div style={{ color: "var(--accent)", marginTop: "4px", fontSize: "0.78rem" }}>
                      ✓ AI suggestions will NOT replace the source answers.
                    </div>
                  </div>
                </div>
              )}

              {bulkConfirmationModal.type === "apply_ai" && (
                <div>
                  <p style={{ marginTop: 0 }}>
                    This will apply the AI answer suggestions across the selected questions.
                  </p>
                  <div style={{ background: "rgba(0,0,0,0.25)", padding: "10px 14px", borderRadius: "8px", margin: "10px 0" }}>
                    <div><strong>Questions affected:</strong> {bulkConfirmationModal.count} of {localQuestions.length}</div>
                  </div>
                  <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: "8px", padding: "10px", color: "#FDE68A", fontSize: "0.80rem" }}>
                    <strong>Explicit Warning:</strong> AI suggestions are not authoritative unless you approve them.
                  </div>
                </div>
              )}

              {bulkConfirmationModal.type === "fill_missing" && (
                <div>
                  <p style={{ marginTop: 0 }}>
                    AI will analyze the available source content and fill eligible missing metadata fields across all questions.
                  </p>
                  <div style={{ background: "rgba(0,0,0,0.25)", padding: "10px 14px", borderRadius: "8px", margin: "10px 0" }}>
                    <div><strong>Questions:</strong> {bulkConfirmationModal.count}</div>
                    <div><strong>Missing fields:</strong> {bulkConfirmationModal.missingFieldsCount ?? 0}</div>
                  </div>
                  <ul style={{ margin: "10px 0 0 0", paddingLeft: "18px", fontSize: "0.78rem", color: "var(--text-muted)", display: "flex", flexDirection: "column", gap: "4px" }}>
                    <li>Never overwrites existing source values.</li>
                    <li>Never invents authoritative source answers.</li>
                    <li>Preserves source answers separately from AI answers.</li>
                    <li>AI-generated values remain marked as AI_INFERRED with individual confidence.</li>
                    <li>Fields that cannot be safely inferred remain MISSING for manual review.</li>
                  </ul>
                </div>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}>
              <button
                type="button"
                className="secondary"
                onClick={() => setBulkConfirmationModal(null)}
                style={{ padding: "8px 16px" }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => {
                  if (bulkConfirmationModal.type === "keep_source") {
                    executeBulkAnswerAction("source");
                  } else if (bulkConfirmationModal.type === "apply_ai") {
                    executeBulkAnswerAction("ai");
                  } else if (bulkConfirmationModal.type === "fill_missing") {
                    setBulkConfirmationModal(null);
                    handleTriggerBatchAIFill();
                  }
                }}
                style={{
                  padding: "8px 18px",
                  background: bulkConfirmationModal.type === "apply_ai" ? "#059669" : "var(--primary)",
                  borderColor: bulkConfirmationModal.type === "apply_ai" ? "#10B981" : "var(--primary-hover)",
                }}
              >
                {bulkConfirmationModal.type === "keep_source"
                  ? "Keep Source Answers for All"
                  : bulkConfirmationModal.type === "apply_ai"
                  ? "Apply AI Suggestions"
                  : "Fill All Missing Fields"}
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
