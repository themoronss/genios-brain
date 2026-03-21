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
  relationship_stage: 'ACTIVE' | 'WARM' | 'NEEDS_ATTENTION' | 'DORMANT' | 'COLD' | 'AT_RISK';
  last_interaction_at: string;
  interaction_count: number;
  sentiment_avg: number;
  entity_type: string;
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
  entity_type: string;
  // V1 Detailing additions
  confidence_score?: number;
  community_id?: number;
  size_score?: number;
  is_bidirectional?: boolean;
  freshness_score?: number;
  composite_score?: number;
  sentiment_trend?: string;
  response_rate?: number;
  avg_response_time_hours?: number;
  human_score?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  strength: number;
  link_type?: 'primary' | 'cc_shared';
  // V1 Detailing additions
  sentiment_trend?: string;
  is_bidirectional?: boolean;
}

export interface CommunityData {
  community_id: number;
  color: string;
  node_count: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  entity_type_counts: Record<string, number>;
  communities?: CommunityData[];
}

export interface EntityDetails {
  name: string;
  company: string | null;
  relationship_stage: string;
  last_interaction: string;
  sentiment_trend: string | number;
  communication_style: string;
  topics_of_interest: string[];
  open_commitments: number | string[];
  open_commitments_detail?: CommitmentDetail[];
  interaction_count: number;
  email?: string;
  what_works?: string;
  what_to_avoid?: string;
  recommended_action?: string;
  // V1 Detailing additions
  confidence?: number;
  sentiment_avg?: number;
  sentiment_ewma?: number;
  interaction_types?: Record<string, number>;
  overdue_commitments?: number;
  response_rate?: number;
  avg_response_time_hours?: number;
  is_bidirectional?: boolean;
}

export interface CommitmentDetail {
  text: string;
  owner: string;
  due_date: string | null;
  status: string;
  is_overdue: boolean;
  is_soft: boolean;
  days_until_due: number | null;
  created_at: string;
}

export interface ContextBundle {
  entity: EntityDetails | null;
  context_for_agent: string;
  confidence: number;
  coverage_score?: number;
  match_confidence?: number;
  matched_from?: string;
  error?: string;
  action_recommendation?: string;
  escalation_recommended?: boolean;
  action_reason?: string;
  scores?: {
    freshness: number;
    confidence: number;
    consistency: number;
    signal: number;
    authority: number;
    composite: number;
  };
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

export interface DashboardMetrics {
  contacts_count: number;
  interactions_count: number;
  active_relationships_count: number;
  context_calls_count: number;
}

export interface ActivityEvent {
  event_type: string;
  event_data: Record<string, any>;
  created_at: string | null;
}
