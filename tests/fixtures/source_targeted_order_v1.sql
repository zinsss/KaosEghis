WITH day_guard AS (
    SELECT CASE WHEN to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                             'YYYYMMDD') = %(day)s THEN 1 ELSE 0 END AS matches
), h AS (
    SELECT recept_no FROM public.h1opdin
    WHERE clinic_ymd = %(day)s AND ptnt_no::text = %(chart_no)s
      AND (SELECT matches FROM day_guard) = 1
    LIMIT %(encounter_limit)s
), o AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no,
           medfee_nm = %(compact_name)s AS compact_match,
           medfee_nm = %(spaced_name)s AS spaced_match,
           ord_cd = %(compact_name)s AS code_match
    FROM public.h2opd_doct_ord child
    WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = child.recept_no)
    LIMIT %(order_limit)s
), summary AS (
    SELECT 'current_day_matches' AS metric, matches::bigint AS n FROM day_guard
    UNION ALL SELECT 'day_encounters', count(*) FROM h
    UNION ALL SELECT 'invalid_encounter_keys', count(*) FROM h
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
    UNION ALL SELECT 'duplicate_encounter_keys', count(*) FROM
        (SELECT recept_no FROM h GROUP BY recept_no HAVING count(*) > 1) d
    UNION ALL SELECT 'linked_orders', count(*) FROM o
    UNION ALL SELECT 'orders_on_day', count(*) FROM o WHERE ord_ymd = %(day)s
    UNION ALL SELECT 'orders_off_day', count(*) FROM o WHERE ord_ymd IS DISTINCT FROM %(day)s
    UNION ALL SELECT 'compact_name_matches', count(*) FROM o WHERE compact_match
    UNION ALL SELECT 'spaced_name_matches', count(*) FROM o WHERE spaced_match
    UNION ALL SELECT 'exact_code_matches', count(*) FROM o WHERE code_match
    UNION ALL SELECT 'invalid_order_keys', count(*) FROM o
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
           OR ord_ymd IS NULL OR btrim(ord_ymd::text) = ''
           OR ord_no IS NULL OR btrim(ord_no::text) = ''
           OR ord_seq_no IS NULL OR btrim(ord_seq_no::text) = ''
    UNION ALL SELECT 'duplicate_order_keys', count(*) FROM
        (SELECT recept_no, ord_ymd, ord_no, ord_seq_no FROM o
         GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1) d
)
SELECT metric, n FROM summary ORDER BY metric
LIMIT 13
