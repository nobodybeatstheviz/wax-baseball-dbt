-- Count of attended games in fct_games must equal count of rows in
-- stg_attended_games. Catches both directions of breakage:
--   - lost attended games (filter logic drift, source data quirk)
--   - phantom attended games (duplicate join, accidental spine swap)
-- Returns 0 rows when healthy.
with attended_in_fct as (

    select count(*) as n from {{ ref('fct_games') }} where was_attended = true

),

attended_in_spine as (

    select count(*) as n from {{ ref('stg_attended_games') }}

)

select
    attended_in_fct.n   as fct_count,
    attended_in_spine.n as spine_count
from attended_in_fct
cross join attended_in_spine
where attended_in_fct.n != attended_in_spine.n
