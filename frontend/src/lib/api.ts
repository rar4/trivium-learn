const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Bearer token shared by every API call; no token means the legacy local learner. */
const TOKEN_KEY = "trivium_token";
export const AUTH_CHANGED_EVENT = "trivium:auth-changed";

export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  email?: string | null;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new CustomEvent(AUTH_CHANGED_EVENT));
}

/** Every backend request carries the active account's bearer token. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || undefined);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (res.status === 401 && token) setAuthToken(null);
  return res;
}


export interface CourseListItem {
  id: number;
  subject: string;
  level: string;
  language?: string;
  access_mode?: "open" | "guided";
  cover_image_url?: string;
  is_completed: boolean;
  source_type?: "web" | "document";
  source_book_filename?: string;
  source_book_pages?: number;
  created_at?: string;
  category?: string;
  // Fog-of-War: totals / percent-to-total are never returned by the API.
}

export interface CatalogCategory {
  id: string;
  label_en: string;
  label_pt: string;
}

export interface CatalogItem {
  id: number;
  subject: string;
  level: string;
  category: string;
  language?: string;
  cover_image_url?: string;
  source_type?: "web" | "document";
  created_at?: string;
}

export interface LessonStepSummary {
  id: number;
  title: string;
  core_concept: string;
  status: "locked" | "in_progress" | "completed";
}

/** Blind navigation pointer — never carries a future title or hook. */
export interface BlindStepPointer {
  id: number;
  status: "locked" | "in_progress" | "completed";
}

export interface StepGates {
  lesson_id: number;
  grammar: boolean;
  logic: boolean;
  rhetoric: boolean;
  lesson_completed: boolean;
  current_stage: "learn" | "quiz" | "simulate" | "teach_back" | "unlock";
  stages?: Array<{ id: string; passed: boolean; available: boolean }>;
  has_simulation?: boolean;
  has_discursive?: boolean;
  has_socratic_duel?: boolean;
  mcq?: { score: number; target: number };
  flashcards?: { score: number; target: number };
  socratic_round?: number;
}

/** The one step the learner is allowed to see right now. */
export interface CurrentStepResponse {
  id: number | null;
  stage: StepGates["current_stage"];
  title: string | null;
  hook: string | null;
  content: string | null;
  gates: StepGates | null;
}

export interface NextStepResponse {
  course_id: number;
  subject: string;
  level: string;
  category: string;
  language?: string;
  fog_of_war: boolean;
  current_step: BlindStepPointer | null;
  completed_lessons: LessonStepSummary[];
  is_course_complete: boolean;
}

export interface LessonGates {
  lesson_id: number;
  grammar: boolean;
  logic: boolean;
  rhetoric: boolean;
  lesson_completed: boolean;
}

export interface ProfileStats {
  xp: number;
  level: number;
  streak_days: number;
  completed_lessons: number;
  badges: string[];
  reviews_completed: number;
  reviews_due: number;
}

export interface CertificateData {
  course_id: number;
  subject: string;
  completed_lessons: number;
  issued_at: string;
  share_id: string;
  share_url: string;
}

export interface CourseSource {
  title: string;
  url: string;
  domain: string;
  description?: string;
  citation?: boolean;
  chapter_index?: number;
  type?: string;
}

export interface CatalogTier {
  id: string;
  label_en: string;
  label_pt: string;
  modules: number;
  lessons_per_module: number;
  total_lessons: number;
}

export interface CatalogPersona {
  id: string;
  label_en: string;
  label_pt: string;
}

export interface CourseSummary {
  id: number;
  subject: string;
  level: string;
  category?: string;
  fog_of_war?: boolean;
  completed_lessons?: LessonStepSummary[];
  next_step?: LessonStepSummary | null;
  language?: string;
  access_mode?: "open" | "guided";
  cover_image_url?: string;
  is_completed: boolean;
  source_type?: "web" | "document";
  source_book_filename?: string;
  source_book_pages?: number;
  research_dossier?: string;
  sources?: CourseSource[];
  modules: ModuleDetail[];
}

export interface ModuleDetail {
  id: number;
  module_number: number;
  title: string;
  is_unlocked: boolean;
  is_completed: boolean;
  lessons: LessonSummary[];
}

export interface LessonSummary {
  id: number;
  lesson_number: number;
  title: string;
  core_concept: string;
  status: "locked" | "in_progress" | "completed";
  mcq_score: number;
  discursive_passed: boolean;
}

export interface IndicatorState {
  name: string;
  value_type?: string; // "percentage" | "label"
  value?: number | string;
  color_hint?: string;
  label?: string;
  value_numeric?: number | null;
  status_level?: string | null;
}

export interface SimulationTurn2Option {
  id: string;
  text?: string;
  action_label?: string;
  outcome_story?: string;
  updated_indicators?: IndicatorState[];
  final_indicators?: IndicatorState[];
  verdict_summary?: string;
  operation_scorecard?: string;
  trade_off_analysis?: string;
  is_success: boolean;
}

export interface SimulationTurn1Option {
  id: string;
  text?: string;
  action_label?: string;
  reaction_story: string;
  collateral_effect?: string;
  updated_indicators: IndicatorState[];
  turn2_prompt: string;
  turn2_options: SimulationTurn2Option[];
}

export interface SimulationSandbox {
  context?: string;
  scenario_title?: string;
  context_description?: string;
  initial_indicators: IndicatorState[];
  turn1_prompt: string;
  turn1_options: SimulationTurn1Option[];
}

export interface SocraticDuelQuestion {
  dilemma_title?: string;
  question: string;
  evaluation_rubric: string[];
  image_url?: string;
  image_caption?: string;
}

export interface SocraticState {
  round1_answer?: string;
  cognitive_knot?: string;
  round1_feedback?: string;
  current_round?: number;
  round2_answer?: string;
  score?: number;
  final_feedback?: string;
  passed?: boolean;
}

export interface MiniProjectBrief {
  title?: string;
  lesson_title?: string;
  prompt: string;
  checklist?: string[];
  deliverable_hint?: string;
}

export interface MiniProjectState {
  available: boolean;
  passed: boolean;
  brief: MiniProjectBrief;
  submission?: string | null;
  feedback?: string | null;
  score?: number | null;
}

export interface LessonFullDetail {
  id: number;
  course_id?: number;
  language?: string;
  module_id: number;
  module_title: string;
  lesson_number: number;
  title: string;
  core_concept: string;
  content_markdown: string;
  quiz?: {
    mcq: Array<{
      question: string;
      options: Array<{ label: string; text: string; is_correct: boolean }>;
      explanation: string;
    }>;
    simulation?: SimulationSandbox;
    socratic_duel?: SocraticDuelQuestion;
    fill_in_the_blanks?: Array<{
      sentence_with_blank: string;
      correct_word: string;
      hint: string;
    }>;
    discursive?: {
      question: string;
      evaluation_rubric: string[];
    };
  };
  status: "locked" | "in_progress" | "completed";
  mcq_score: number;
  blanks_score: number;
  discursive_passed: boolean;
  discursive_feedback?: string;
  simulation_passed?: boolean;
  socratic_passed?: boolean;
  socratic_state?: SocraticState | null;
  mini_project?: MiniProjectState | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: "processing" | "completed" | "failed";
  progress_pct: number;
  current_step: string;
  course_id?: number;
  error_message?: string;
}

export async function createCourse(
  subject: string,
  level: string = "Básico",
  language: string = "pt-BR",
  persona: string = "auto"
): Promise<{ job_id: string }> {
  try {
    const res = await apiFetch(`/api/courses/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject, level, language, persona }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Falha ao iniciar criação do curso" }));
      throw new Error(err.detail || "Falha ao iniciar criação do curso");
    }
    return res.json();
  } catch (err: unknown) {
    if (err instanceof TypeError && (err.message === "Failed to fetch" || err.message.includes("fetch"))) {
      throw new Error("Não foi possível conectar ao servidor backend (porta 8000). Verifique se o Trivium está em execução.");
    }
    throw err;
  }
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await apiFetch(`/api/jobs/${jobId}`);
  if (!res.ok) throw new Error("Falha ao consultar status do job");
  return res.json();
}

export async function getCourses(): Promise<CourseListItem[]> {
  const res = await apiFetch(`/api/courses`);
  if (!res.ok) throw new Error("Falha ao listar cursos");
  return res.json();
}

export async function getCourse(courseId: number): Promise<CourseSummary> {
  const res = await apiFetch(`/api/courses/${courseId}`);
  if (!res.ok) throw new Error("Falha ao carregar curso");
  return res.json();
}

export async function getCatalogCategories(): Promise<CatalogCategory[]> {
  const res = await apiFetch(`/api/catalog/categories`);
  if (!res.ok) throw new Error("Falha ao carregar categorias");
  return res.json();
}

export async function getCatalogTiers(): Promise<CatalogTier[]> {
  const res = await apiFetch(`/api/catalog/tiers`);
  if (!res.ok) throw new Error("Falha ao carregar níveis de geração");
  return res.json();
}

export async function getCatalogPersonas(): Promise<CatalogPersona[]> {
  const res = await apiFetch(`/api/catalog/personas`);
  if (!res.ok) throw new Error("Falha ao carregar personas");
  return res.json();
}

export async function getCatalog(params?: { category?: string; q?: string; difficulty?: string }): Promise<CatalogItem[]> {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.q) qs.set("q", params.q);
  if (params?.difficulty) qs.set("difficulty", params.difficulty);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await apiFetch(`/api/catalog${suffix}`);
  if (!res.ok) throw new Error("Falha ao carregar catálogo");
  return res.json();
}

export async function getNextStep(courseId: number): Promise<NextStepResponse> {
  const res = await apiFetch(`/api/courses/${courseId}/next-step`);
  if (!res.ok) throw new Error("Falha ao carregar próximo passo");
  return res.json();
}

export async function getCurrentStep(courseId: number): Promise<CurrentStepResponse> {
  const res = await apiFetch(`/api/courses/${courseId}/current-step`);
  if (!res.ok) throw new Error("Falha ao carregar passo atual");
  return res.json();
}

export async function getLessonGates(lessonId: number): Promise<LessonGates> {
  const res = await apiFetch(`/api/lessons/${lessonId}/gates`);
  if (!res.ok) throw new Error("Falha ao carregar gates");
  return res.json();
}

export async function getProfileStats(): Promise<ProfileStats> {
  const res = await apiFetch(`/api/profile/stats`);
  if (!res.ok) throw new Error("Falha ao carregar perfil");
  return res.json();
}

export async function recordActivity(): Promise<void> {
  try {
    await apiFetch(`/api/profile/activity`, { method: "POST" });
  } catch { /* best-effort streak */ }
}

export async function getCertificate(courseId: number): Promise<CertificateData> {
  const res = await apiFetch(`/api/courses/${courseId}/certificate`);
  if (!res.ok) throw new Error("Certificado ainda não disponível");
  return res.json();
}

export async function getLesson(lessonId: number): Promise<LessonFullDetail> {
  const res = await apiFetch(`/api/lessons/${lessonId}`);
  if (!res.ok) throw new Error("Falha ao carregar detalhes da aula");
  return res.json();
}

export async function submitQuiz(
  lessonId: number,
  answers: Record<string, string>,
  blanks: Record<string, string>
) {
  const res = await apiFetch(`/api/lessons/${lessonId}/submit-quiz`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lesson_id: lessonId, answers, blanks }),
  });
  if (!res.ok) throw new Error("Falha ao submeter quiz");
  return res.json();
}

export async function submitDiscursive(lessonId: number, answer: string) {
  const res = await apiFetch(`/api/lessons/${lessonId}/submit-discursive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lesson_id: lessonId, answer }),
  });
  if (!res.ok) throw new Error("Falha ao submeter resposta discursiva");
  return res.json();
}

export async function submitSimulation(
  lessonId: number,
  turn1Id: string,
  turn2Id: string,
  isSuccess: boolean = true
) {
  const res = await apiFetch(`/api/lessons/${lessonId}/submit-simulation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ turn1_id: turn1Id, turn2_id: turn2Id, is_success: isSuccess }),
  });
  if (!res.ok) throw new Error("Falha ao submeter simulação");
  return res.json();
}

export async function submitSocraticDuel(
  lessonId: number,
  round: number,
  answer: string
) {
  const res = await apiFetch(`/api/lessons/${lessonId}/socratic-duel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ round, answer }),
  });
  if (!res.ok) throw new Error("Falha ao submeter round do duelo socrático");
  return res.json();
}

export function getLessonPdfUrl(lessonId: number): string {
  return `${API_BASE_URL}/api/lessons/${lessonId}/download-pdf`;
}

export async function deleteCourse(courseId: number): Promise<{ success: boolean; message: string }> {
  const res = await apiFetch(`/api/courses/${courseId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Falha ao excluir curso" }));
    throw new Error(err.detail || "Falha ao excluir curso");
  }
  return res.json();
}

export interface SettingsData {
  image_provider: "openai" | "fal" | "google" | "huggingface" | "disabled" | string;
  image_aspect_ratio: "1:1" | "16:9" | "4:3";
  image_quality: "standard" | "hd" | "fast";
  image_model?: string;
  has_fal_api_key?: boolean;
  fal_api_key_preview?: string;
  has_hf_token: boolean;
  hf_token_preview: string;
  has_gemini_api_key: boolean;
  gemini_api_key_preview: string;
  has_openai_api_key: boolean;
  openai_api_key_preview: string;
  has_openrouter_api_key: boolean;
  openrouter_api_key_preview: string;
  has_anthropic_api_key: boolean;
  anthropic_api_key_preview: string;
  llm_provider: "openrouter" | "openai" | "anthropic" | "local" | "ollama";
  openai_models: string;
  anthropic_models: string;
  openrouter_models: string;
  local_base_url?: string;
  local_models?: string;
  has_local_api_key?: boolean;
  local_api_key_preview?: string;
}

export interface SettingsUpdateData {
  image_provider?: string;
  image_aspect_ratio?: string;
  image_quality?: string;
  image_model?: string;
  fal_api_key?: string;
  hf_token?: string;
  gemini_api_key?: string;
  openai_api_key?: string;
  openrouter_api_key?: string;
  anthropic_api_key?: string;
  llm_provider?: "openrouter" | "openai" | "anthropic" | "local" | "ollama";
  openai_models?: string;
  anthropic_models?: string;
  openai_model?: string;
  anthropic_model?: string;
  openrouter_models?: string;
  local_base_url?: string;
  local_models?: string;
  local_api_key?: string;
}

export interface LocalConnectionTestResult {
  online: boolean;
  provider_detected: "ollama" | "lm_studio" | "vllm" | "generic" | "offline";
  base_url: string;
  models: string[];
  latency_ms: number;
  error?: string;
  message?: string;
}

export async function testLocalConnection(baseUrl?: string, apiKey?: string): Promise<LocalConnectionTestResult> {
  const res = await apiFetch(`/api/settings/test-local-connection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Falha ao testar conexão local" }));
    throw new Error(err.detail || "Falha ao testar conexão local");
  }
  return res.json();
}

export async function getSettings(): Promise<SettingsData> {
  const res = await apiFetch(`/api/settings`);
  if (!res.ok) throw new Error("Falha ao carregar configurações");
  return res.json();
}

export async function updateSettings(data: SettingsUpdateData): Promise<SettingsData> {
  const res = await apiFetch(`/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Falha ao salvar configurações");
  return res.json();
}

export interface BenchmarkModelItem {
  model: string;
  success: boolean;
  latency: number;
  score?: number;
  words?: number;
  compliance?: string;
  json_ready?: boolean;
  sample?: string;
  error?: string;
}

export interface BenchmarkResult {
  total_scanned: number;
  approved_count: number;
  rejected_count: number;
  benchmark_duration_seconds: number;
  recommended_csv: string;
  approved_models: BenchmarkModelItem[];
  rejected_models: BenchmarkModelItem[];
}

export async function runFreeModelsBenchmark(): Promise<BenchmarkResult> {
  const res = await apiFetch(`/api/settings/benchmark-free-models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Falha ao executar benchmark" }));
    throw new Error(err.detail || "Falha ao executar benchmark de modelos");
  }
  return res.json();
}

export interface LessonChatMessageItem {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

export async function getLessonChatHistory(lessonId: number): Promise<LessonChatMessageItem[]> {
  const res = await apiFetch(`/api/lessons/${lessonId}/chat`);
  if (!res.ok) throw new Error("Falha ao carregar histórico do chat");
  return res.json();
}

export async function sendLessonChatMessage(lessonId: number, message: string): Promise<LessonChatMessageItem> {
  const res = await apiFetch(`/api/lessons/${lessonId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Falha ao enviar mensagem" }));
    throw new Error(err.detail || "Falha ao comunicar com o Tutor");
  }
  return res.json();
}

export async function clearLessonChatHistory(lessonId: number): Promise<{ status: string }> {
  const res = await apiFetch(`/api/lessons/${lessonId}/chat`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Falha ao limpar histórico do chat");
  return res.json();
}

export async function updateCourseAccessMode(
  courseId: number, 
  accessMode: "open" | "guided"
): Promise<{ success: boolean; access_mode: "open" | "guided" }> {
  const res = await apiFetch(`/api/courses/${courseId}/access-mode`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_mode: accessMode }),
  });
  if (!res.ok) throw new Error("Falha ao atualizar modo de acesso do curso");
  return res.json();
}

export interface DocumentUploadResponse {
  doc_id: string;
  clean_title: string;
  author?: string;
  format: string;
  total_pages: number;
  total_chapters: number;
  total_word_count: number;
  inferred_level: string;
  complexity_reason: string;
  reader_prerequisites: string[];
  raw_filename: string;
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiFetch(`/api/courses/upload-document`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Falha ao processar arquivo" }));
    throw new Error(err.detail || "Falha ao enviar e analisar arquivo");
  }
  return res.json();
}

export async function generateCourseFromDocument(
  docId: string,
  subject?: string,
  level?: string,
  language: string = "pt-BR",
  persona: string = "auto"
): Promise<{ job_id: string; status: string; message: string }> {
  try {
    const res = await apiFetch(`/api/courses/generate-from-document`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_id: docId, subject, level, language, persona }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Falha ao iniciar geração a partir do documento" }));
      throw new Error(err.detail || "Falha ao iniciar curso");
    }
    return res.json();
  } catch (err: unknown) {
    if (err instanceof TypeError && (err.message === "Failed to fetch" || err.message.includes("fetch"))) {
      throw new Error("Não foi possível conectar ao servidor backend (porta 8000). Verifique se o Trivium está em execução.");
    }
    throw err;
  }
}

/* ------------------------ accounts / progress ------------------------ */

async function parseAuthResponse(res: Response): Promise<AuthResponse> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Authentication failed");
  return data as AuthResponse;
}

export async function registerUser(
  username: string,
  password: string,
  displayName?: string,
  email?: string
): Promise<AuthResponse> {
  return parseAuthResponse(await apiFetch(`/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, display_name: displayName, email }),
  }));
}

export async function loginUser(username: string, password: string): Promise<AuthResponse> {
  return parseAuthResponse(await apiFetch(`/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }));
}

export async function logoutUser(): Promise<void> {
  try { await apiFetch(`/api/auth/logout`, { method: "POST" }); } catch { /* best effort */ }
  setAuthToken(null);
}

export async function getAuthMe(): Promise<AuthUser> {
  const res = await apiFetch(`/api/auth/me`);
  if (!res.ok) throw new Error("Not signed in");
  return res.json();
}

export interface ReviewItem {
  id: number;
  lesson_id: number;
  item_key: string | null;
  kind: string | null;
  prompt: string | null;
  expected: string | null;
  due_on: string;
  interval_days: number;
  misses: number;
}

/** Only already-mastered work plus items that are due for review. */
export interface MasteryDashboard {
  display_name: string;
  xp: number;
  level: number;
  reviewable_items: ReviewItem[];
  mastered_by_skill: Array<{
    category: string;
    mastered_items: Array<{
      id: number;
      title: string;
      core_concept: string;
      course: string | null;
      completed_on: string | null;
    }>;
  }>;
}

export async function getMasteryDashboard(): Promise<MasteryDashboard> {
  const res = await apiFetch(`/api/dashboard/mastery`);
  if (!res.ok) throw new Error("Não foi possível carregar o painel de domínio");
  return res.json();
}

export async function completeReview(itemId: number, passed: boolean): Promise<{ next_due_on: string }> {
  const res = await apiFetch(`/api/reviews/${itemId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ passed }),
  });
  if (!res.ok) throw new Error("Falha ao registrar revisão");
  return res.json();
}

/** Authenticated PDF download (bearer token cannot travel in an <a href>). */
export async function downloadLessonPdf(lessonId: number): Promise<void> {
  const res = await apiFetch(`/api/lessons/${lessonId}/download-pdf`);
  if (!res.ok) throw new Error("Falha ao baixar o PDF da aula");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `trivium-lesson-${lessonId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Rhetoric Express: lesson-scoped build/present brief + saved artifact. */
export async function getMiniProject(lessonId: number): Promise<MiniProjectState> {
  const res = await apiFetch(`/api/lessons/${lessonId}/mini-project`);
  if (!res.ok) throw new Error("Failed to load the mini-project brief");
  return res.json();
}

export async function submitMiniProject(
  lessonId: number,
  submission: string,
): Promise<{ success: boolean; mini_project_passed: boolean; passed: boolean; score: number; feedback: string }> {
  const res = await apiFetch(`/api/lessons/${lessonId}/mini-project`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ submission }),
  });
  if (!res.ok) throw new Error("Failed to submit the mini-project");
  return res.json();
}

/** Personal notes booklet (Markdown) with this lesson's teach-back work. */
export async function downloadLessonNotes(lessonId: number): Promise<void> {
  const res = await apiFetch(`/api/lessons/${lessonId}/export-notes`);
  if (!res.ok) throw new Error("Failed to download notes");
  const disposition = res.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = match ? match[1] : `trivium-notes-${lessonId}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Post-hoc mastery report (only earned work, never future steps). */
export async function downloadMasteryReport(): Promise<void> {
  const res = await apiFetch("/api/dashboard/mastery/report");
  if (!res.ok) throw new Error("Failed to download the mastery report");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "trivium-mastery-report.md";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}




