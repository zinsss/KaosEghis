WITH h AS (
    SELECT recept_no FROM public.h1opdin
    WHERE clinic_ymd = %(day)s AND ptnt_no::text = %(chart_no)s
      AND to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD') = %(read_day)s
    LIMIT 2
), o AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no,
           user_cd = %(expected_code)s AS code_matches,
           user_nm = %(expected_name)s AS name_matches
    FROM public.h2opd_doct_ord child
    WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = child.recept_no)
    LIMIT 2
)
SELECT (SELECT count(*) FROM h) AS encounters, count(*) AS orders,
       count(CASE WHEN recept_no IS NULL OR btrim(recept_no::text) = ''
                    OR ord_ymd IS NULL OR btrim(ord_ymd::text) = ''
                    OR ord_no IS NULL OR btrim(ord_no::text) = ''
                    OR ord_seq_no IS NULL OR btrim(ord_seq_no::text) = '' THEN 1 END) AS invalid_keys,
       count(CASE WHEN ord_ymd IS DISTINCT FROM %(day)s THEN 1 END) AS off_day,
       count(CASE WHEN code_matches THEN 1 END) AS expected_code_matches,
       count(CASE WHEN name_matches THEN 1 END) AS expected_name_matches
FROM o
LIMIT 2
