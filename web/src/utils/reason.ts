export const REASON_TEXT: Record<string, string> = {
  BUFFER_BREACH: 'Paying would breach the liquidity floor',
  DISCOUNT_CAPTURED: 'Early-payment discount captured',
  DISCOUNT_FORGONE: 'Discount forgone — liquidity preserved instead',
  PENALTY_AVOIDED: 'Penalty avoided by paying on time',
  PENALTY_ACCEPTED: 'Penalty accepted — cheaper than the alternative',
  FACILITY_LIMIT: 'Facility headroom exhausted',
  OBLIGATION_PRIORITY: 'Cash reserved for an upcoming hard obligation',
  SUPPLIER_CRITICAL: 'Strategic supplier — prioritised for relationship',
  SUPPLIER_DISTRESS: 'Supplier under liquidity stress — early payment',
  CHEAPER_FINANCING: 'Borrowing is cheaper than forgoing the discount',
  INSUFFICIENT_CASH: 'Insufficient cash for this action',
  NO_BETTER_ALTERNATIVE: 'No better alternative exists',
};

export const ACTION_TEXT: Record<string, string> = {
  PAY_NOW: 'Pay now from cash',
  PAY_EARLY_DISCOUNT: 'Pay early to capture discount',
  PAY_AT_MATURITY: 'Pay at maturity',
  DELAY: 'Delay payment',
  FINANCE_BANK: 'Finance via bank line',
  FINANCE_SUPPLIER: 'Finance via supplier program',
  HOLD: 'Hold — revisit next cycle',
};

export const ACTION_COLOR: Record<string, string> = {
  PAY_NOW: 'accent',
  PAY_EARLY_DISCOUNT: 'accent',
  PAY_AT_MATURITY: 'info',
  DELAY: 'warning',
  FINANCE_BANK: 'purple',
  FINANCE_SUPPLIER: 'purple',
  HOLD: 'muted',
};

export const EVENT_TEXT: Record<string, string> = {
  DAY_ADVANCED: 'Day advanced',
  RECEIVABLE_DELAYED: 'Receivable delayed',
  RECEIVABLE_COLLECTED: 'Receivable collected',
  NEW_INVOICE: 'New invoice received',
  INVOICE_PAID: 'Invoice paid',
  RATE_CHANGE: 'Financing rate changed',
  NEW_OBLIGATION: 'New obligation added',
  SUPPLIER_DISTRESS: 'Supplier under distress',
  CASH_INJECTION: 'Cash injection received',
};
