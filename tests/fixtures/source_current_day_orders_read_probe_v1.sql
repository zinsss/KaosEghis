-- CONTROLLED ONE-SHOT EVIDENCE ONLY. No source authority or runtime approval.
WITH scope AS (
    SELECT statement_timestamp() AS observed_at,
           CASE WHEN to_char(timezone('Asia/Seoul', statement_timestamp()),
                             'YYYYMMDD') = %(day)s THEN TRUE ELSE FALSE END AS day_matches,
           CASE WHEN %(encounter_cap)s BETWEEN 1 AND 10000
                     AND %(order_cap)s BETWEEN 1 AND 100000
                THEN TRUE ELSE FALSE END AS limits_valid
), h AS (
    SELECT clinic_ymd, recept_no, proc_gb, hold_yn
    FROM public.h1opdin
    WHERE clinic_ymd = %(day)s
      AND (SELECT day_matches AND limits_valid FROM scope)
    LIMIT (CASE WHEN (SELECT limits_valid FROM scope) THEN %(encounter_cap)s + 1 ELSE 0 END)
), o AS (
    SELECT TRUE AS child_present, recept_no, ord_ymd, ord_no, ord_seq_no,
           ord_cd, medfee_nm, user_cd, user_nm, qty, divide, days,
           ord_type, proc_dept_cd, dc_yn, act_yn
    FROM public.h2opd_doct_ord AS child
    WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = child.recept_no)
    LIMIT (CASE WHEN (SELECT limits_valid FROM scope) THEN %(order_cap)s + 1 ELSE 0 END)
), checks AS (
    SELECT (SELECT count(*) FROM h) AS encounter_count,
           (SELECT count(*) FROM o) AS order_count,
           (SELECT count(*) FROM h
            WHERE NOT EXISTS (SELECT 1 FROM o WHERE o.recept_no = h.recept_no))
               AS no_order_encounter_count,
           EXISTS (SELECT 1 FROM h
                   WHERE recept_no IS NULL OR trim(CAST(recept_no AS text)) = '')
               AS invalid_encounter_key,
           EXISTS (SELECT 1 FROM h GROUP BY recept_no HAVING count(*) > 1)
               AS duplicate_encounter_key,
           EXISTS (SELECT 1 FROM o
                   WHERE recept_no IS NULL OR trim(CAST(recept_no AS text)) = ''
                      OR ord_ymd IS NULL OR trim(CAST(ord_ymd AS text)) = ''
                      OR ord_no IS NULL OR trim(CAST(ord_no AS text)) = ''
                      OR ord_seq_no IS NULL OR trim(CAST(ord_seq_no AS text)) = '')
               AS invalid_order_key,
           EXISTS (SELECT 1 FROM o
                   GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1)
               AS duplicate_order_key,
           EXISTS (SELECT 1 FROM o WHERE ord_ymd IS NULL OR ord_ymd <> %(day)s)
               AS off_day_child,
           EXISTS (SELECT 1 FROM h WHERE hold_yn IS NULL OR hold_yn NOT IN ('Y', 'N'))
               OR EXISTS (SELECT 1 FROM o
                          WHERE dc_yn IS NULL OR dc_yn NOT IN ('Y', 'N')
                             OR act_yn IS NULL OR act_yn NOT IN ('Y', 'N'))
               AS invalid_retained_flag,
           EXISTS (SELECT 1 FROM h WHERE char_length(CAST(recept_no AS text)) > 128
                       OR char_length(CAST(proc_gb AS text)) > 128)
               OR EXISTS (SELECT 1 FROM o
                          WHERE char_length(CAST(recept_no AS text)) > 128
                             OR char_length(CAST(ord_no AS text)) > 128
                             OR char_length(CAST(ord_seq_no AS text)) > 128
                             OR char_length(ord_cd) > 128 OR char_length(medfee_nm) > 256
                             OR char_length(user_cd) > 128 OR char_length(user_nm) > 256
                             OR char_length(ord_type) > 128 OR char_length(proc_dept_cd) > 128
                             OR char_length(CAST(qty AS text)) > 128
                             OR char_length(CAST(divide AS text)) > 128
                             OR char_length(CAST(days AS text)) > 128)
               AS field_overflow
), gate AS (
    SELECT scope.observed_at, scope.day_matches, checks.encounter_count,
           checks.order_count, checks.no_order_encounter_count,
           CASE WHEN NOT scope.limits_valid THEN 'invalid_limits'
                WHEN NOT scope.day_matches THEN 'wrong_day'
                WHEN checks.encounter_count > %(encounter_cap)s THEN 'encounter_overflow'
                WHEN checks.order_count > %(order_cap)s THEN 'order_overflow'
                WHEN checks.invalid_encounter_key THEN 'invalid_encounter_key'
                WHEN checks.duplicate_encounter_key THEN 'duplicate_encounter_key'
                WHEN checks.invalid_order_key THEN 'invalid_order_key'
                WHEN checks.duplicate_order_key THEN 'duplicate_order_key'
                WHEN checks.off_day_child THEN 'off_day_child'
                WHEN checks.invalid_retained_flag THEN 'invalid_retained_flag'
                WHEN checks.field_overflow THEN 'field_overflow'
                ELSE 'candidate_rows' END AS extraction_status
    FROM scope CROSS JOIN checks
)
SELECT CASE WHEN h.recept_no IS NULL THEN 'META' ELSE 'DATA' END AS row_kind,
       gate.extraction_status, gate.observed_at, gate.day_matches,
       gate.encounter_count, gate.order_count, gate.no_order_encounter_count,
       CASE WHEN gate.extraction_status <> 'candidate_rows' OR gate.encounter_count = 0
            THEN 1 ELSE gate.order_count + gate.no_order_encounter_count END AS expected_result_rows,
       h.clinic_ymd AS source_clinic_day, h.recept_no AS source_encounter_id,
       h.proc_gb AS source_reception_code, h.hold_yn AS hold_yn,
       CASE WHEN o.child_present THEN TRUE ELSE FALSE END AS order_present,
       o.recept_no AS source_order_encounter_id, o.ord_ymd AS source_order_date,
       o.ord_no AS source_order_number, o.ord_seq_no AS source_order_sequence,
       o.ord_cd AS catalog_code, o.medfee_nm AS catalog_name,
       o.user_cd AS user_code, o.user_nm AS user_name,
       o.qty AS source_qty, o.divide AS source_divide, o.days AS source_days,
       o.ord_type AS order_type, o.proc_dept_cd AS department_code,
       o.dc_yn AS dc_yn, o.act_yn AS act_yn
FROM gate
LEFT JOIN h ON gate.extraction_status = 'candidate_rows'
LEFT JOIN o ON o.recept_no = h.recept_no
ORDER BY h.recept_no, o.ord_ymd, o.ord_no, o.ord_seq_no
