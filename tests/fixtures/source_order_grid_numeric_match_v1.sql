WITH h AS (
    SELECT recept_no FROM public.h1opdin
    WHERE clinic_ymd = %(day)s AND ptnt_no::text = %(chart_no)s
      AND to_char(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul', 'YYYYMMDD') = %(day)s
    LIMIT 2
), o AS (
    SELECT recept_no, ord_ymd, ord_no, ord_seq_no,
           qty = %(daily)s AS daily_matches,
           divide = %(frequency)s AS frequency_matches,
           days = %(days)s AS days_matches,
           pg_typeof(qty)::text AS qty_type,
           pg_typeof(divide)::text AS divide_type,
           pg_typeof(days)::text AS days_type
    FROM public.h2opd_doct_ord child
    WHERE EXISTS (SELECT 1 FROM h WHERE h.recept_no = child.recept_no)
      AND child.user_cd = %(code)s AND child.user_nm = %(name)s
    LIMIT 2
)
SELECT (SELECT count(*) FROM h) AS encounters, count(*) AS matching_orders,
       count(CASE WHEN recept_no IS NULL OR btrim(recept_no::text) = ''
                    OR ord_ymd IS NULL OR btrim(ord_ymd::text) = ''
                    OR ord_no IS NULL OR btrim(ord_no::text) = ''
                    OR ord_seq_no IS NULL OR btrim(ord_seq_no::text) = '' THEN 1 END) AS invalid_keys,
       count(CASE WHEN ord_ymd IS DISTINCT FROM %(day)s THEN 1 END) AS off_day,
       count(CASE WHEN daily_matches THEN 1 END) AS daily_matches,
       count(CASE WHEN frequency_matches THEN 1 END) AS frequency_matches,
       count(CASE WHEN days_matches THEN 1 END) AS days_matches,
       min(qty_type), min(divide_type), min(days_type)
FROM o
LIMIT 2
