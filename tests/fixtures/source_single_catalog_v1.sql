WITH h AS (
    SELECT recept_no FROM public.h1opdin
    WHERE clinic_ymd = %(day)s AND ptnt_no::text = %(chart_no)s
      AND to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD') = %(read_day)s
    LIMIT 2
), o AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no, ord_cd, medfee_nm
    FROM public.h2opd_doct_ord child
    WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = child.recept_no)
    LIMIT 2
), counts AS (
    SELECT (SELECT count(*) FROM h) AS encounters, count(*) AS orders,
           count(CASE WHEN recept_no IS NULL OR btrim(recept_no::text) = ''
                        OR ord_ymd IS NULL OR btrim(ord_ymd::text) = ''
                        OR ord_no IS NULL OR btrim(ord_no::text) = ''
                        OR ord_seq_no IS NULL OR btrim(ord_seq_no::text) = '' THEN 1 END) AS invalid_keys,
           count(CASE WHEN ord_ymd IS DISTINCT FROM %(day)s THEN 1 END) AS off_day,
           count(CASE WHEN length(ord_cd::text) > 64 OR length(medfee_nm::text) > 256
                        OR ord_cd::text ~ '[[:cntrl:]]' OR medfee_nm::text ~ '[[:cntrl:]]'
                        OR ord_cd::text ~ '[0-9]{6}[- ]?[1-8][0-9]{6}'
                        OR medfee_nm::text ~ '[0-9]{6}[- ]?[1-8][0-9]{6}'
                        OR ord_cd::text ~ '01[016789][- ]?[0-9]{3,4}[- ]?[0-9]{4}'
                        OR medfee_nm::text ~ '01[016789][- ]?[0-9]{3,4}[- ]?[0-9]{4}' THEN 1 END) AS withheld
    FROM o
)
SELECT encounters, orders, invalid_keys, off_day, withheld,
       CASE WHEN encounters = 1 AND orders = 1 AND invalid_keys = 0 AND off_day = 0 AND withheld = 0
            THEN (SELECT max(ord_cd::text) FROM o) END AS catalog_code,
       CASE WHEN encounters = 1 AND orders = 1 AND invalid_keys = 0 AND off_day = 0 AND withheld = 0
            THEN (SELECT max(medfee_nm::text) FROM o) END AS catalog_name
FROM counts
LIMIT 2
