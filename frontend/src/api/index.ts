/**
 * MemoFlow API client — V3
 * All fetch calls centralized here. Base URL is proxied via Vite to localhost:8000.
 */

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  // Only set Content-Type for non-FormData bodies; FormData needs browser-generated boundary
  const headers: HeadersInit = options?.body instanceof FormData
    ? { ...options?.headers }
    : { 'Content-Type': 'application/json', ...options?.headers }
  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...options,
  })
  if (!res.ok) {
    // 会话过期/未登录 → 去登录页（登录接口自身的 401 除外，由登录页展示错误）
    if (res.status === 401 && !path.startsWith('/auth/') && window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

// ─── Auth ─────────────────────────────────────────────────

export function login(username: string, password: string, remember: boolean) {
  return request<{ message: string; remember_days: number }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password, remember }),
  })
}

export function logout() {
  return request<{ message: string }>('/auth/logout', { method: 'POST' })
}

// ─── Types ────────────────────────────────────────────────

export interface Block {
  id: number
  source_id: number
  sequence_number: number
  content: string
  quiz: string
  reps: number
  interval: number
  ease_factor: number
  last_review: string | null
  next_review: string | null
  is_suspended: boolean
  notes?: { zh: string; en: string }[] | null
  stability?: number | null   // FSRS 记忆稳定性
  difficulty?: number | null  // FSRS 难度（1~10）
}

export interface SourceListItem {
  id: number
  title: string
  source_type: string
  created_at: string
  block_count: number
  deck_id: number | null
}

export interface SourceImportResponse {
  source_id: number
  title: string
  block_count: number
  blocks: Block[]
  deck_id: number | null
  warning: string | null
}

export interface MarkdownImportResponse {
  deck_id: number
  deck_name: string
  file_name: string
  total_sources: number
  total_cards: number
  sources: Array<{ source_id: number; title: string; card_count: number }>
}

export interface ReviewNextResponse {
  block: Block | null
  batch: Block[] | null
  remaining: number
  is_new: boolean
  source_title: string | null
  deck_name: string | null
  review_mode: string
  predicted_intervals: Record<string, string> | null
}

export interface ReviewSubmitResponse {
  block_id: number
  new_interval: number
  new_ease_factor: number
  next_review: string
  message: string
  leech?: boolean  // 水蛭卡：反复忘记，建议编辑或暂停
}

export interface BatchReviewSubmitResponse {
  updated_count: number
  new_interval: number
  new_ease_factor: number
  next_review: string
  message: string
}

export interface Stats {
  total: number
  mastered: number
  learning: number
  new: number
  due_today: number
}

export interface Deck {
  id: number
  name: string
  path: string
  parent_id: number | null
  parser_config: {
    strategy: string
    source_lang: string
    target_lang: string
    custom_prompt: string | null
  }
  card_order: string
  created_at: string
}

// ─── Decks ────────────────────────────────────────────────

export function fetchDecks() {
  return request<Deck[]>('/decks')
}

export function createDeck(data: {
  name: string
  parent_path?: string | null
  parser_config?: object | null
  card_order?: string
}) {
  return request<Deck>('/decks', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateDeck(deckId: number, data: {
  name?: string
  parser_config?: object
  card_order?: string
}) {
  return request<Deck>(`/decks/${deckId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteDeck(deckId: number) {
  return request<{ message: string; success: boolean }>(`/decks/${deckId}`, {
    method: 'DELETE',
  })
}

// ─── Review ───────────────────────────────────────────────

export function fetchNextCard(deckId?: number | null, excludeBlockId?: number) {
  const params = new URLSearchParams()
  if (deckId != null) {
    params.set('deck_id', String(deckId))
    params.set('include_children', 'true')
  }
  if (excludeBlockId != null) params.set('exclude_block_id', String(excludeBlockId))
  const q = params.toString()
  return request<ReviewNextResponse>(`/review/next${q ? `?${q}` : ''}`)
}

export function submitReview(blockId: number, quality: number) {
  return request<ReviewSubmitResponse>(`/review/${blockId}`, {
    method: 'POST',
    body: JSON.stringify({ quality }),
  })
}

export function submitBatchReview(blockIds: number[], overallQuality: number) {
  return request<BatchReviewSubmitResponse>(`/review/batch`, {
    method: 'POST',
    body: JSON.stringify({ block_ids: blockIds, overall_quality: overallQuality }),
  })
}

// ─── Import ───────────────────────────────────────────────

export interface CardCandidate {
  content: string
  quiz: string
}

export interface SourcePreviewResponse {
  title: string
  deck_id: number | null
  cards: CardCandidate[]
  warning: string | null
}

/** LLM 拆解预览（不入库），供编辑/剔除后确认导入 */
export function previewSource(text: string, title?: string, deckId?: number | null) {
  return request<SourcePreviewResponse>('/sources/preview', {
    method: 'POST',
    body: JSON.stringify({ text, title: title || undefined, deck_id: deckId ?? undefined }),
  })
}

export function importSource(
  text: string,
  title?: string,
  deckId?: number | null,
  cards?: CardCandidate[],  // 预览确认后的卡片；提供时后端跳过 LLM
) {
  return request<SourceImportResponse>('/sources/import', {
    method: 'POST',
    body: JSON.stringify({ text, title: title || undefined, source_type: 'text', deck_id: deckId ?? undefined, cards }),
  })
}

export interface BlockContextItem {
  id: number
  sequence_number: number
  content: string
  quiz: string
  is_current: boolean
}

export function fetchBlockContext(blockId: number, radius = 2) {
  return request<BlockContextItem[]>(`/blocks/${blockId}/context?radius=${radius}`)
}

/** 水蛭卡清单 {block_id: 忘记次数} */
export function fetchLeeches() {
  return request<Record<string, number>>('/stats/leeches')
}

export function importMarkdownFile(file: File, deckId: number) {
  const form = new FormData()
  form.append('file', file)
  form.append('deck_id', String(deckId))
  return request<MarkdownImportResponse>('/sources/import-markdown', {
    method: 'POST',
    body: form,
  })
}

export interface UrlPreviewResponse {
  title: string
  text: string
  url: string
  char_count: number
}

export function fetchUrlPreview(url: string) {
  return request<UrlPreviewResponse>('/sources/fetch-url', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

// ─── Library ──────────────────────────────────────────────

export function fetchBlocks(params?: { deck_id?: number | null; source_id?: number; skip?: number; limit?: number }) {
  const q = new URLSearchParams()
  if (params?.deck_id != null) q.set('deck_id', String(params.deck_id))
  if (params?.source_id) q.set('source_id', String(params.source_id))
  if (params?.skip)      q.set('skip', String(params.skip))
  if (params?.limit)     q.set('limit', String(params.limit))
  return request<Block[]>(`/blocks${q.toString() ? '?' + q : ''}`)
}

export function deleteBlock(blockId: number) {
  return request<{ message: string; success: boolean }>(`/blocks/${blockId}`, {
    method: 'DELETE',
  })
}

export function updateBlock(blockId: number, data: { content?: string; quiz?: string; is_suspended?: boolean; notes?: { zh: string; en: string }[] }) {
  return request<Block>(`/blocks/${blockId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

// ─── Stats ────────────────────────────────────────────────

export function fetchStats(deckId?: number | null) {
  const q = deckId != null ? `?deck_id=${deckId}&include_children=true` : ''
  return request<Stats>(`/stats${q}`)
}

export interface ReviewHistoryDay {
  date: string   // "YYYY-MM-DD"
  count: number
}

export interface TodaySummary {
  reviewed: number
  again: number
  retention: number | null
  streak: number
  remaining: number
  due_tomorrow: number
}

// ─── Settings ─────────────────────────────────────────────

export interface ReviewSettings {
  new_quota_unit: 'cards' | 'articles'
  new_per_day: number
}

export function fetchReviewSettings() {
  return request<ReviewSettings>('/settings/review')
}

export function updateReviewSettings(data: ReviewSettings) {
  return request<ReviewSettings>('/settings/review', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function undoReview(blockId: number) {
  return request<{ block_id: number; message: string }>(`/review/${blockId}/undo`, {
    method: 'POST',
  })
}

export function fetchTodaySummary(deckId?: number | null) {
  const q = deckId != null ? `?deck_id=${deckId}&include_children=true` : ''
  return request<TodaySummary>(`/stats/today${q}`)
}

export function fetchReviewHistory(days = 90, deckId?: number | null) {
  const params = new URLSearchParams({ days: String(days) })
  if (deckId != null) {
    params.set('deck_id', String(deckId))
    params.set('include_children', 'true')
  }
  return request<ReviewHistoryDay[]>(`/stats/history?${params}`)
}

export interface SourceDetail {
  id: number
  title: string
  source_type: string
  url: string | null
  original_text: string
  created_at: string
  deck_id: number | null
  blocks: Block[]
}

export function fetchSourceDetail(sourceId: number) {
  return request<SourceDetail>(`/sources/${sourceId}`)
}

export function relearnSource(sourceId: number) {
  return request<{ message: string }>(`/sources/${sourceId}/relearn`, { method: 'POST' })
}

export function fetchSources() {
  return request<SourceListItem[]>('/sources')
}
