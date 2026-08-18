export type Question = {
  question: string;
  topic: string;
  subtopic: string;
  answer_1: string;
  answer_2: string;
  answer_3: string;
  answer_4: string;
  difficulty: "Easy" | "Medium" | "Hard";
  correct_answer: string;
  score: number;
};
