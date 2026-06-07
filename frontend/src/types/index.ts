// Scholar V1 — TypeScript types mirroring backend schemas

export type SourceType = "pdf" | "url";
export type IngestionStatus = "pending" | "indexing_pageindex" | "indexing_vectors" | "ready" | "failed";
export type GoalLevel = "beginner" | "intermediate" | "advanced";
export type SessionStatus = "pending" | "in_progress" | "complete";
export type RetrievalStrategy = "pageindex" | "vector" | "hybrid";

export interface KnowledgeSource {
  id: string;
  title: string;
  source_type: SourceType;
  file_path?: string;
  url?: string;
  page_count: number;
  pageindex_doc_id?: string;
  status: IngestionStatus;
  created_at: string;
}

export interface StudyGoal {
  id: string;
  title: string;
  topic: string;
  knowledge_source_ids: string[];
  deadline_days: number;
  level: GoalLevel;
  sessions_per_week: number;
  status: "active" | "complete";
  created_at: string;
  notion_page_url?: string | null;
}

export interface StudySession {
  id: string;
  goal_id: string;
  session_number: number;
  title: string;
  topic: string;
  estimated_minutes: number;
  status: SessionStatus;
  quiz_score?: number;
  notes_markdown?: string;
  created_at: string;
}

export interface StudyPlan {
  goal: StudyGoal;
  sessions: StudySession[];
  total_sessions: number;
  completed_sessions: number;
}

export interface RetrievedChunk {
  source_id: string;
  source_title: string;
  content: string;
  page_number?: number;
  section_title?: string;
  relevance_score: number;
  retrieval_method: RetrievalStrategy;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations: RetrievedChunk[];
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  // correct_index intentionally omitted — sent only after submission
  explanation?: string;
}

export interface QuizResult {
  score: number;
  total_questions: number;
  correct_count: number;
  per_question: Array<{
    question_id: string;
    correct: boolean;
    explanation: string;
  }>;
  followup_session_added?: boolean;
  followup_session?: StudySession | null;
}

export interface TestQuestion {
  id: string;
  session_number: number;
  question: string;
  options: string[];
  // correct_index intentionally omitted — never sent to frontend
}

export interface TestResult {
  score: number;
  total_questions: number;
  correct_count: number;
  goal_complete: boolean;
  weak_session_numbers: number[];
  per_question: Array<{
    question_id: string;
    correct: boolean;
    explanation: string;
  }>;
}

// ─── Dashboard / summary shapes (GET /goals, GET /super/threads) ───────────────

export interface GoalSummary {
  id: string;
  title: string;
  topic: string;
  level: string;
  status: string;
  created_at: string | null;
  deadline_days: number;
  total_sessions: number;
  completed_sessions: number;
}

export interface SuperThreadSummary {
  thread_id: string;
  title: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface SuperThreadMessage {
  role: string;
  content: string;
}

export interface SuperThreadDetail {
  thread_id: string;
  title: string | null;
  messages: SuperThreadMessage[];
}
