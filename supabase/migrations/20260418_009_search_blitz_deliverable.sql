-- © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
-- FlatFinder™ — Search Blitz deliverable (Pattern B: Perplexity report after fulfillment)

ALTER TABLE search_blitz_orders
  ADD COLUMN IF NOT EXISTS deliverable_report TEXT,
  ADD COLUMN IF NOT EXISTS matched_listing_ids UUID[],
  ADD COLUMN IF NOT EXISTS fulfillment_error TEXT;

COMMENT ON COLUMN search_blitz_orders.deliverable_report IS 'Markdown (or plain) renter-facing report from Perplexity after fulfillment.';
COMMENT ON COLUMN search_blitz_orders.matched_listing_ids IS 'Listing UUIDs included in the Blitz snapshot sent to the model.';
COMMENT ON COLUMN search_blitz_orders.fulfillment_error IS 'Set when status=failed after an attempted internal fulfill run.';
