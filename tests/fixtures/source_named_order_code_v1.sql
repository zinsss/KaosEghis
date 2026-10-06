WITH day_guard AS (
    SELECT CASE WHEN to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                             'YYYYMMDD') = %(day)s THEN 1 ELSE 0 END AS matches
), h AS (
    SELECT recept_no FROM public.h1opdin
    WHERE clinic_ymd = %(day)s AND (SELECT matches FROM day_guard) = 1
    LIMIT %(encounter_limit)s
), matched AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no,
           ord_type, proc_dept_cd, dc_yn, act_yn,
           CASE WHEN medfee_nm = %(compact_name)s THEN 'COMPACT_NAME'
                WHEN medfee_nm = %(spaced_name)s THEN 'SPACED_NAME'
                WHEN medfee_nm IS NULL THEN 'NULL_NAME'
                ELSE 'OTHER_NAME' END AS name_match
    FROM public.h2opd_doct_ord o
    WHERE ord_cd = %(order_code)s AND ord_ymd = %(day)s
      AND EXISTS (SELECT 1 FROM h WHERE h.recept_no = o.recept_no)
    LIMIT %(order_limit)s
), summary AS (
    SELECT 'current_day_matches' AS metric, matches::bigint AS n FROM day_guard
    UNION ALL SELECT 'encounters_in_scope', count(*) FROM h
    UNION ALL SELECT 'invalid_encounter_keys', count(*) FROM h
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
    UNION ALL SELECT 'duplicate_encounter_keys', count(*) FROM
        (SELECT recept_no FROM h GROUP BY recept_no HAVING count(*) > 1) d
    UNION ALL SELECT 'matched_orders', count(*) FROM matched
    UNION ALL SELECT 'matched_encounters', count(DISTINCT recept_no) FROM matched
    UNION ALL SELECT 'invalid_order_keys', count(*) FROM matched
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
           OR ord_ymd IS NULL OR btrim(ord_ymd::text) = ''
           OR ord_no IS NULL OR btrim(ord_no::text) = ''
           OR ord_seq_no IS NULL OR btrim(ord_seq_no::text) = ''
    UNION ALL SELECT 'duplicate_order_keys', count(*) FROM
        (SELECT recept_no, ord_ymd, ord_no, ord_seq_no FROM matched
         GROUP BY recept_no, ord_ymd, ord_no, ord_seq_no HAVING count(*) > 1) d
), safe AS (
    SELECT name_match,
           CASE WHEN ord_type IS NULL THEN 'NULL'
                WHEN ord_type::text = '' THEN 'BLANK'
                WHEN ord_type::text = ANY(%(types)s) THEN ord_type::text
                ELSE 'UNREVIEWED' END AS kind,
           CASE WHEN proc_dept_cd IS NULL THEN 'NULL'
                WHEN proc_dept_cd::text = '' THEN 'BLANK'
                WHEN proc_dept_cd::text = ANY(%(departments)s) THEN proc_dept_cd::text
                ELSE 'UNREVIEWED' END AS department,
           CASE WHEN dc_yn IS NULL THEN 'NULL'
                WHEN dc_yn::text = '' THEN 'BLANK'
                WHEN dc_yn::text = ANY(%(flags)s) THEN dc_yn::text
                ELSE 'UNREVIEWED' END AS dc,
           CASE WHEN act_yn IS NULL THEN 'NULL'
                WHEN act_yn::text = '' THEN 'BLANK'
                WHEN act_yn::text = ANY(%(flags)s) THEN act_yn::text
                ELSE 'UNREVIEWED' END AS act
    FROM matched
), buckets AS (
    SELECT name_match, kind, department, dc, act, count(*) AS n FROM safe
    GROUP BY name_match, kind, department, dc, act
), report AS (
    SELECT 'summary' AS section, metric, '' AS code, '' AS kind,
           '' AS department, '' AS dc, '' AS act, n FROM summary
    UNION ALL SELECT 'bucket', name_match, 'CONFIRMED_CODE', kind, department, dc, act, n FROM buckets
)
SELECT section, metric, code, kind, department, dc, act, n FROM report
ORDER BY section DESC, metric, code, kind, department, dc, act
LIMIT 41
