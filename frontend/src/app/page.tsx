"use client";

import { useState } from "react";
import type { Question } from "../types";
import { exportQuestions, generate, regenerate } from "../lib/api";

export default function Home() {
  const [template, setTemplate] = useState<File | null>(null);
  const [source, setSource] = useState<File | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [difficulty, setDifficulty] = useState("Auto");
  const [count, setCount] = useState(5);
  const [score, setScore] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onGenerate() {
    if (!template || !source) return setError("Please upload both the template and source file.");
    setLoading(true); setError("");
    try {
      const result = await generate(template, source, count, difficulty, score);
      setQuestions(result.questions);
      setColumns(result.columns);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally { setLoading(false); }
  }

  async function onRegenerate(index: number) {
    setLoading(true); setError("");
    try {
      const q = await regenerate(questions[index]);
      setQuestions(prev => prev.map((item, i) => i === index ? q : item));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Regeneration failed");
    } finally { setLoading(false); }
  }

  function update(index: number, key: keyof Question, value: string | number) {
    setQuestions(prev => prev.map((q, i) => i === index ? { ...q, [key]: value } as Question : q));
  }

  async function onExport(format: "csv" | "xlsx") {
    try {
      const blob = await exportQuestions(questions, columns, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `questions_generated.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  }

  return (
    <main className="container">
      <h1>Universal Question Generator</h1>
      <p>Upload a question template and source material, generate CET-style MCQs, review them, and export.</p>

      <section className="card">
        <h2>1. Upload files</h2>
        <div className="row">
          <label>Template (CSV/XLSX)<br /><input type="file" accept=".csv,.xlsx,.xls" onChange={e => setTemplate(e.target.files?.[0] || null)} /></label>
          <label>Source (PDF/TXT/CSV/XLSX)<br /><input type="file" accept=".pdf,.txt,.csv,.xlsx,.xls" onChange={e => setSource(e.target.files?.[0] || null)} /></label>
        </div>
      </section>

      <section className="card">
        <h2>2. Generation settings</h2>
        <div className="row">
          <label>Difficulty<br />
            <select value={difficulty} onChange={e => setDifficulty(e.target.value)}>
              <option>Auto</option><option>Easy</option><option>Medium</option><option>Hard</option>
            </select>
          </label>
          <label>Questions<br /><input type="number" min={1} max={100} value={count} onChange={e => setCount(Number(e.target.value))} /></label>
          <label>Score<br /><input type="number" min={0} value={score} onChange={e => setScore(Number(e.target.value))} /></label>
        </div>
        <br />
        <button className="primary" onClick={onGenerate} disabled={loading}>
          {loading ? "Processing..." : "Generate Questions"}
        </button>
        {error && <p className="error">{error}</p>}
      </section>

      {questions.length > 0 && (
        <section className="card">
          <div className="row" style={{justifyContent: "space-between", alignItems: "center"}}>
            <div><h2>3. Review questions</h2><p>{questions.length} questions generated.</p></div>
            <div className="row">
              <button onClick={() => onExport("xlsx")}>Download Excel</button>
              <button onClick={() => onExport("csv")}>Download CSV</button>
            </div>
          </div>

          <div style={{overflowX: "auto"}}>
            <table>
              <thead><tr>
                <th>#</th><th>Question</th><th>Topic</th><th>Sub Topic</th>
                <th>Answer 1</th><th>Answer 2</th><th>Answer 3</th><th>Answer 4</th>
                <th>Difficulty</th><th>Correct Answer</th><th>Score</th><th>Action</th>
              </tr></thead>
              <tbody>
                {questions.map((q, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    {(["question","topic","subtopic","answer_1","answer_2","answer_3","answer_4"] as const).map(key =>
                      <td key={key}><textarea value={q[key]} onChange={e => update(i, key, e.target.value)} /></td>
                    )}
                    <td>
                      <select value={q.difficulty} onChange={e => update(i, "difficulty", e.target.value)}>
                        <option>Easy</option><option>Medium</option><option>Hard</option>
                      </select>
                    </td>
                    <td><input value={q.correct_answer} onChange={e => update(i, "correct_answer", e.target.value)} /></td>
                    <td><input type="number" value={q.score} onChange={e => update(i, "score", Number(e.target.value))} /></td>
                    <td><button onClick={() => onRegenerate(i)} disabled={loading}>Regenerate</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
