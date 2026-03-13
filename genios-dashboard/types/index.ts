export interface User {
  id: string;
  org_id: string;
  email: string;
  name: string;
  token?: string;
}

export interface Contact {
  id: string;
  name: string;
  email: string;
  company: string | null;
  relationship_stage: 'ACTIVE' | 'WARM' | 'DORMANT' | 'COLD' | 'AT_RISK';
  last_interaction_at: string;
  interaction_count: number;
  sentiment_avg: number;
}

export interface GraphNode {
  id: string;
  name: string;
  company: string | null;
  relationship_stage: string;
  last_interaction_days: number;
  sentiment_avg: number;
  interaction_count: number;
  email: string;
}

export interface GraphLink {
  source: string;
  target: string;
  strength: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface EntityDetails {
  name: string;
  company: string | null;
  relationship_stage: string;
  last_interaction: string;
  sentiment_trend: string | number;
  communication_style: string;
  topics_of_interest: string[];
  open_commitments: string[];
  interaction_count: number;
  email?: string;
  what_works?: string;
  what_to_avoid?: string;
  recommended_action?: string;
}

export interface ContextBundle {
  entity: EntityDetails | null;
  context_for_agent: string;
  confidence: number;
  match_confidence?: number;
  matched_from?: string;
  error?: string;
}

export interface ConnectionStatus {
  gmail_connected: boolean;
  last_sync: string | null;
  contacts_count: number;
  interactions_count: number;
  ingestion_complete: boolean;
  ingestion_progress: number;
  sync_status: 'idle' | 'running' | 'completed' | 'error';
  sync_total: number;
  sync_processed: number;
  sync_error: string | null;
}

export interface DraftResponse {
  draft: string;
  context_used: string;
  confidence: number;
  entity_name: string;
}
