export interface HealthcareAgent {
  id: string;
  domain_key: string;
  name: string;
  specialty: string;
  description: string;
  system_prompt: string;
  icon: string;
  color: string;
  is_active: boolean;
  created_at: string;
}

export interface ChatSessionItem {
  id: string;
  agent_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentItem {
  id: string;
  agent_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'deleting';
  error_message?: string | null;
  summary?: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface CitationItem {
  citation_number: number;
  document_id?: string | null;
  chunk_id?: string | null;
  filename: string;
  page_number?: number | null;
  excerpt: string;
  score: number;
  chunk_type: string;
  image_path?: string | null;
  sources: string[];
}

export interface GraphTripleItem {
  source: string;
  source_type?: string;
  relationship: string;
  target: string;
  target_type?: string;
  confidence?: number;
}

export interface MatchedKeywordItem {
  term: string;
  category?: string;
  source?: string;
  count?: number;
}

export interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: CitationItem[];
  graph_triples?: GraphTripleItem[];
  matched_keywords?: MatchedKeywordItem[];
  visual_payload?: {
    mermaid?: string;
    katex?: string;
    chart?: Array<Record<string, unknown>>;
    graph_triples?: GraphTripleItem[];
    matched_keywords?: MatchedKeywordItem[];
  } | null;
  follow_up_suggestions?: string[];
  isStreaming?: boolean;
  created_at?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}
