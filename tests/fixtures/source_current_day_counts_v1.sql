WITH day_guard AS (
    SELECT CASE WHEN to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul',
                             'YYYYMMDD') = %(day)s THEN 1 ELSE 0 END AS matches
), h AS (
    SELECT recept_no, proc_gb, hold_yn
    FROM public.h1opdin
    WHERE clinic_ymd = %(day)s AND (SELECT matches FROM day_guard) = 1
    LIMIT %(encounter_limit)s
), buckets AS (
    SELECT CASE WHEN proc_gb IS NULL THEN 'NULL'
                WHEN proc_gb::text = '' THEN 'BLANK'
                WHEN proc_gb::text = ANY(%(codes)s) THEN proc_gb::text
                ELSE 'UNREVIEWED' END AS code,
           CASE WHEN hold_yn IS NULL THEN 'NULL'
                WHEN hold_yn::text = '' THEN 'BLANK'
                WHEN hold_yn::text = ANY(%(flags)s) THEN hold_yn::text
                ELSE 'UNREVIEWED' END AS hold,
           CASE WHEN EXISTS (
               SELECT 1 FROM public.h2opd_doct_ord o WHERE o.recept_no = h.recept_no
           ) THEN 'WITH_ORDERS' ELSE 'WITHOUT_ORDERS' END AS presence
    FROM h
), summary AS (
    SELECT 'current_day_matches' AS metric, matches::bigint AS n FROM day_guard
    UNION ALL SELECT 'encounters', count(*) FROM h
    UNION ALL SELECT 'invalid_encounter_keys', count(*) FROM h
        WHERE recept_no IS NULL OR btrim(recept_no::text) = ''
    UNION ALL SELECT 'duplicate_encounter_keys', count(*) FROM
        (SELECT recept_no FROM h GROUP BY recept_no HAVING count(*) > 1) d
)
SELECT 'summary' AS section, metric AS code, ''::text AS hold,
       ''::text AS presence, n FROM summary
UNION ALL SELECT 'bucket', code, hold, presence, count(*) FROM buckets
    GROUP BY code, hold, presence
ORDER BY 1, 2, 3, 4
LIMIT 95
