-- RenewFlow reference views (MySQL 8). Documentation artifacts: the app does not run them.
-- Each view maps to a reason code and a dashboard metric, and works as a Metabase question.
-- Thresholds (12 hours) match the app's default stuck threshold.
-- Note: SQL joins are exact. The id-typo healing and homoglyph normalisation in the engine are not reproduced here, so
-- v_orphaned_invoices shows the "plain join" number (3 on the sample) and the engine shows the healed number (2).

-- Reason code: LINK_ORPHAN_INVOICE. Metric: Orphaned Invoice Rate (plain join).
CREATE OR REPLACE VIEW v_orphaned_invoices AS
SELECT i.id AS invoice_id, i.invoice_number, i.net_amount, i.paid_at,
       TIMESTAMPDIFF(HOUR, i.paid_at, NOW()) AS hours_since_payment
FROM invoices i
LEFT JOIN faculty_form_unapproved f ON f.invoice_id = i.id AND f.deleted_at IS NULL
WHERE i.deleted_at IS NULL AND i.is_renewal = 'Yes' AND i.payment_status IN ('Paid', 'Partially_Paid') AND f.id IS NULL;

-- Metric: Form Backlog over 12h (Ops approval queue).
CREATE OR REPLACE VIEW v_pending_forms_over_12h AS
SELECT f.id AS form_id, f.invoice_id, f.educator_id, f.created_at,
       TIMESTAMPDIFF(HOUR, f.created_at, NOW()) AS hours_waiting
FROM faculty_form_unapproved f
WHERE f.deleted_at IS NULL AND f.approval_status = 'Pending' AND f.created_at < NOW() - INTERVAL 12 HOUR;

-- Reason codes: BOOKING_STUCK_RESCUED, BATCH_FULL_FALSE_POSITIVE. Metric: Unscheduled Booking Rate over 12h.
CREATE OR REPLACE VIEW v_unscheduled_bookings AS
SELECT b.id AS booking_request_id, b.invoice_id, b.request_status, b.classbatch_id, b.created_at,
       TIMESTAMPDIFF(HOUR, b.created_at, NOW()) AS hours_waiting
FROM booking_requests b
LEFT JOIN class_schedule_bookings s ON s.invoice_id = b.invoice_id AND s.deleted_at IS NULL AND s.is_cancelled = 'No'
WHERE b.deleted_at IS NULL AND b.request_status <> 'Completed' AND s.id IS NULL AND b.created_at < NOW() - INTERVAL 12 HOUR;

-- Reason code: BATCH_FULL_FALSE_POSITIVE. Metric: False Batch-Full Rate.
-- A same-batch renewal fails as full although the student already holds a seat in that batch.
CREATE OR REPLACE VIEW v_false_batch_full AS
SELECT b.id AS booking_request_id, b.invoice_id, b.student_id, b.classbatch_id, r.active_students_count, r.max_batch_size
FROM booking_requests b
JOIN reference_active_batches_and_students r
  ON r.student_id = b.student_id AND r.current_classbatch_id = b.classbatch_id AND r.deleted_at IS NULL
WHERE b.deleted_at IS NULL AND b.request_status = 'Failed_Batch_Full' AND b.continue_same_batch = 'Yes';

-- Reason code: LINK_DUPLICATE_FORM. Metric: Duplicate Form Rate.
CREATE OR REPLACE VIEW v_duplicate_forms AS
SELECT f.invoice_id, COUNT(*) AS forms, GROUP_CONCAT(f.id ORDER BY f.created_at) AS form_ids
FROM faculty_form_unapproved f
WHERE f.deleted_at IS NULL AND f.invoice_id IS NOT NULL
GROUP BY f.invoice_id HAVING COUNT(*) > 1;

-- Headline SLA: Payment-to-Schedule Turnaround (hours), completed renewals only.
CREATE OR REPLACE VIEW v_payment_to_schedule_tat AS
SELECT i.id AS invoice_id, i.paid_at, MIN(s.created_at) AS first_schedule_row_at,
       ROUND(TIMESTAMPDIFF(MINUTE, i.paid_at, MIN(s.created_at)) / 60, 2) AS hours_payment_to_schedule
FROM invoices i
JOIN class_schedule_bookings s ON s.invoice_id = i.id AND s.deleted_at IS NULL
WHERE i.deleted_at IS NULL AND i.paid_at IS NOT NULL
GROUP BY i.id, i.paid_at;

-- Reason code: DISCOUNT_UNAPPROVED. Metric: Unauthorized Discount Rate. Add an approver column to invoices to close this gap.
CREATE OR REPLACE VIEW v_discounts_without_approval AS
SELECT i.id AS invoice_id, i.invoice_number, i.amount, i.discount_amount, i.net_amount,
       ROUND(i.discount_amount / i.amount * 100, 1) AS discount_percent
FROM invoices i
WHERE i.deleted_at IS NULL AND i.discount_amount > 0;

-- Reason codes: PAY_PARTIAL, PAY_AMOUNT_MISMATCH. Teacher-typed amount differs from what was collected.
CREATE OR REPLACE VIEW v_amount_mismatch AS
SELECT f.id AS form_id, f.invoice_id, f.amount_paid AS form_amount, i.net_amount AS invoice_net, i.payment_status
FROM faculty_form_unapproved f
JOIN invoices i ON i.id = f.invoice_id
WHERE f.deleted_at IS NULL AND i.deleted_at IS NULL AND ABS(f.amount_paid - i.net_amount) > 0.01;

-- Reason code: PAY_NOT_CONFIRMED. Forms filed on invoices that are not paid.
CREATE OR REPLACE VIEW v_forms_on_unpaid_invoices AS
SELECT f.id AS form_id, f.invoice_id, i.payment_status, f.created_at
FROM faculty_form_unapproved f
JOIN invoices i ON i.id = f.invoice_id
WHERE f.deleted_at IS NULL AND i.deleted_at IS NULL AND i.payment_status NOT IN ('Paid', 'Partially_Paid');
