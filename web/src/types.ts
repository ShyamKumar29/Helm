// Data contracts — field names are snake_case and frozen to match contracts/*.
// Never camelCase these. See HELM.md section 4.

export interface Supplier {
  id: string;
  name: string;
  criticality: number;
  liquidity_stress: number;
  supplier_finance_eligible: boolean;
}

export interface Customer {
  id: string;
  name: string;
  mean_delay_days: number;
  std_delay_days: number;
  on_time_probability: number;
  historical_delays: number[];
}

export type InvoiceStatus = 'OPEN' | 'PAID' | 'DELAYED';

export interface Invoice {
  id: string;
  supplier_id: string;
  amount: number;
  issue_date: string;
  due_date: string;
  discount_pct: number;
  discount_until: string;
  penalty_bps_per_day: number;
  max_delay_days: number;
  status: InvoiceStatus;
}

export interface Receivable {
  id: string;
  customer_id: string;
  amount: number;
  expected_date: string;
  status: 'OPEN' | 'COLLECTED';
}

export interface Obligation {
  id: string;
  label: string;
  category: string;
  amount: number;
  due_date: string;
  hard: boolean;
}

export interface Facility {
  id: string;
  type: string;
  limit: number;
  drawn: number;
  apr_pct: number;
  min_draw: number;
  repayment_days: number;
  eligible_supplier_ids: string[] | null;
}

export interface State {
  as_of: string;
  sim_day: number;
  cash_available: number;
  suppliers: Supplier[];
  customers: Customer[];
  invoices: Invoice[];
  receivables: Receivable[];
  obligations: Obligation[];
  facilities: Facility[];
}

export interface ForecastBucket {
  date: string;
  day_offset: number;
  p10: number;
  p50: number;
  p90: number;
  shortfall_prob: number;
  committed_outflow: number;
  expected_inflow: number;
}

export interface Forecast {
  generated_at: string;
  sim_day: number;
  horizon_days: number;
  n_paths: number;
  risk_alpha: number;
  buckets: ForecastBucket[];
  deployable_cash: number;
  buffer_required: number;
  binding_date: string;
  binding_reason: string;
  worst_case_min_cash: number;
}

export type ActionType =
  | 'PAY_NOW'
  | 'PAY_EARLY_DISCOUNT'
  | 'PAY_AT_MATURITY'
  | 'DELAY'
  | 'FINANCE_BANK'
  | 'FINANCE_SUPPLIER'
  | 'HOLD';

export interface RejectedAlternative {
  action: ActionType;
  net_value: number;
  delta: number;
  reason_code: string;
}

export interface ScoreBreakdown {
  discount_captured: number;
  penalty_incurred: number;
  financing_cost: number;
  liquidity_risk_cost: number;
  supplier_stress_delta: number;
  net_value: number;
}

export interface Action {
  action_id: string;
  target_type: string;
  target_id: string;
  supplier_id: string;
  action: ActionType;
  amount: number;
  execute_on: string;
  funding_source: string;
  facility_id: string | null;
  confidence: number;
  score_breakdown: ScoreBreakdown;
  binding_constraints: string[];
  primary_reason_code: string;
  rejected_alternatives: RejectedAlternative[];
  status: string;
}

export interface FacilityAction {
  facility_id: string;
  action: string;
  amount: number;
  expected_repay_date: string;
  interest_cost: number;
}

export interface DecisionTrigger {
  type: string;
  event_id: string | null;
  materiality_score: number;
  description: string;
}

export interface DiffFromPrevious {
  previous_decision_id: string | null;
  flipped: { target_id: string; from: ActionType; to: ActionType; reason_code: string }[];
  added: string[];
  removed: string[];
}

export interface Solver {
  method: string;
  status: string;
  solve_ms: number;
  n_scenarios: number;
  fallback_used: boolean;
}

export interface ObjectiveWeights {
  discount: number;
  financing_cost: number;
  penalty: number;
  liquidity_risk: number;
  supplier_stress: number;
}

export interface DecisionObject {
  decision_id: string;
  run_at: string;
  sim_day: number;
  policy: 'AGENT' | 'BASELINE';
  trigger: DecisionTrigger;
  cash_before: number;
  buffer_required: number;
  deployable_cash: number;
  objective_weights: ObjectiveWeights;
  objective_value: number;
  actions: Action[];
  facility_actions: FacilityAction[];
  solver: Solver;
  diff_from_previous: DiffFromPrevious;
  explanation: Explanation | null;
}

export interface Explanation {
  decision_id: string;
  headline: string;
  narrative: string;
  key_assumptions: string[];
  tradeoffs: string[];
  would_change_if: string[];
  generated_by: string;
  grounded_fields: string[];
}

export interface HelmEvent {
  event_id: string;
  sim_day: number;
  date: string;
  type: string;
  source: string;
  payload: Record<string, unknown>;
  materiality_score: number;
  triggered_reoptimization: boolean;
  triggered_decision_id: string | null;
}

export interface PolicyMetrics {
  discounts_captured: number;
  financing_cost: number;
  penalties_paid: number;
  net_working_capital_cost: number;
  shortfall_days: number;
  min_cash_seen: number;
  obligations_missed: number;
  avg_supplier_stress: number;
  decisions_made: number;
  reoptimizations_triggered: number;
  health_score: number;
  savings_per_day: number;
}

export interface ComparisonMetrics {
  sim_day: number;
  as_of: string;
  agent: PolicyMetrics;
  baseline: PolicyMetrics;
  delta: {
    net_working_capital_cost: number;
    shortfall_days: number;
    obligations_missed: number;
    health_score: number;
  };
}

export type AgentStatus = 'RUNNING' | 'RE-OPTIMIZING';
