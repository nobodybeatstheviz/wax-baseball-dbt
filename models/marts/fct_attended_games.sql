{{ config(materialized='view') }}

-- Compatibility view over fct_games. Preserves the column contract for downstream
-- consumers (Sigma data model, Claude Agent SDK, ad-hoc queries) that referenced
-- fct_attended_games before the 2026-05-28 split into game-grain (fct_games) and
-- play-grain (fct_plays) marts. The was_attended filter does the work that the
-- INNER JOIN used to do.
select * from {{ ref('fct_games') }}
where was_attended = true
