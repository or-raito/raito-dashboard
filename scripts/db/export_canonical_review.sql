-- Export canonical_sp_id mappings for review
-- Run: psql "postgresql://raito_app:raito_app@127.0.0.1:5432/raito" -f export_canonical_review.sql

-- 1. Summary by customer
SELECT
    c.name_en as customer,
    count(*) as alias_count,
    count(DISTINCT alias.canonical_sp_id) as unique_canonicals
FROM sale_points alias
JOIN sale_points canon ON alias.canonical_sp_id = canon.id
LEFT JOIN customers c ON alias.customer_id = c.id
WHERE alias.canonical_sp_id IS NOT NULL
GROUP BY c.name_en
ORDER BY alias_count DESC;

-- 2. Full detail: alias → canonical with customer
\copy (SELECT alias.id as alias_id, alias.branch_name_he as alias_name, canon.id as canonical_id, canon.branch_name_he as canonical_name, c.name_en as customer FROM sale_points alias JOIN sale_points canon ON alias.canonical_sp_id = canon.id LEFT JOIN customers c ON alias.customer_id = c.id WHERE alias.canonical_sp_id IS NOT NULL ORDER BY c.name_en, canon.branch_name_he, alias.branch_name_he) TO '/tmp/canonical_review.csv' WITH CSV HEADER;

-- 3. Self-references (should be cleaned up)
SELECT id, branch_name_he
FROM sale_points
WHERE canonical_sp_id = id;
