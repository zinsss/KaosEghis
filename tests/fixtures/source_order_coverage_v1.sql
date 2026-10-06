WITH day_guard AS (
    SELECT CASE WHEN to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                             'YYYYMMDD') = %(day)s THEN 1 ELSE 0 END AS matches
), h AS (
    SELECT recept_no FROM public.h1opdin
    WHERE clinic_ymd = %(day)s AND (SELECT matches FROM day_guard) = 1
    LIMIT %(encounter_limit)s
), linked AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no FROM public.h2opd_doct_ord o
    WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = o.recept_no)
    LIMIT %(order_limit)s
), dated AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no FROM public.h2opd_doct_ord
    WHERE ord_ymd = %(day)s AND (SELECT matches FROM day_guard) = 1
    LIMIT %(order_limit)s
), summary AS (
    SELECT 'current_day_matches' AS metric, matches::bigint AS n FROM day_guard
    UNION ALL SELECT 'encounters', count(*) FROM h
    UNION ALL SELECT 'encounters_with_orders', count(*) FROM h
        WHERE EXISTS (SELECT 1 FROM linked o WHERE o.recept_no = h.recept_no)
    UNION ALL SELECT 'encounters_without_orders', count(*) FROM h
        WHERE NOT EXISTS (SELECT 1 FROM linked o WHERE o.recept_no = h.recept_no)
    UNION ALL SELECT 'invalid_encounter_keys', count(*) FROM h
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
    UNION ALL SELECT 'duplicate_encounter_keys', count(*) FROM
        (SELECT recept_no FROM h GROUP BY recept_no HAVING count(*) > 1) d
    UNION ALL SELECT 'linked_orders', count(*) FROM linked
    UNION ALL SELECT 'dated_orders', count(*) FROM dated
    UNION ALL SELECT 'linked_orders_on_day', count(*) FROM linked WHERE ord_ymd = %(day)s
    UNION ALL SELECT 'linked_orders_off_day', count(*) FROM linked
        WHERE ord_ymd IS DISTINCT FROM %(day)s
    UNION ALL SELECT 'dated_orders_with_day_encounter', count(*) FROM dated o
        WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = o.recept_no)
    UNION ALL SELECT 'dated_orders_without_day_encounter', count(*) FROM dated o
        WHERE NOT EXISTS (SELECT 1 FROM h WHERE h.recept_no = o.recept_no)
    UNION ALL SELECT 'linked_invalid_keys', count(*) FROM linked
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
           OR ord_ymd IS NULL OR btrim(ord_ymd::text) = ''
           OR ord_no IS NULL OR btrim(ord_no::text) = ''
           OR ord_seq_no IS NULL OR btrim(ord_seq_no::text) = ''
    UNION ALL SELECT 'dated_invalid_keys', count(*) FROM dated
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
           OR ord_ymd IS NULL OR btrim(ord_ymd::text) = ''
           OR ord_no IS NULL OR btrim(ord_no::text) = ''
           OR ord_seq_no IS NULL OR btrim(ord_seq_no::text) = ''
    UNION ALL SELECT 'linked_duplicate_keys', count(*) FROM
        (SELECT recept_no, ord_ymd, ord_no, ord_seq_no FROM linked
         GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1) d
    UNION ALL SELECT 'dated_duplicate_keys', count(*) FROM
        (SELECT recept_no, ord_ymd, ord_no, ord_seq_no FROM dated
         GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1) d
    UNION ALL SELECT 'linked_three_part_multi_date_keys', count(*) FROM
        (SELECT recept_no, ord_no, ord_seq_no FROM linked
         GROUP BY recept_no, ord_no, ord_seq_no HAVING count(DISTINCT ord_ymd) > 1) d
)
SELECT metric, n FROM summary ORDER BY metric
LIMIT 18
