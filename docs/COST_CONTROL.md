# Cost control

`BudgetPolicy` blocks generation before execution when estimated spend would exceed
`MAX_COST_PER_VIDEO` or `MAX_DAILY_GENERATION_COST`. Each generation job records provider,
model, estimate, actual recorded spend and attempt. The synthetic provider costs zero.

For Runway V3, `RunwayProvider.estimate_cost()` derives the estimate from the normalized
billable shot duration. The pipeline preflights the sum of every shot in the entire attempt
before the first paid provider call, then checks each shot again immediately before its
request. This prevents a partially generated paid video when the planned attempt is already
over budget.

The initial manual Runway workflow sets both the per-video and daily generation ceilings to
the explicit workflow input (default: USD 5.00). With the V3 storyboard constrained to 3-4
shots and each shot capped at 10 seconds, the configured Gen-4.5 rate keeps one first-pass
attempt below that default ceiling. A second full paid attempt cannot begin after the first
has consumed the daily ceiling.

Production follow-up: persist the cost ledger transactionally, reconcile estimated versus
provider-reported actual costs when available, cap retries per failure category and alert on
spend anomalies.
