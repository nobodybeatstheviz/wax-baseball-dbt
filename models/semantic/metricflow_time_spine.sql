-- The date spine MetricFlow requires before any metric resolves (P1 finding,
-- 2026-08-31). Range comfortably brackets the attended-games era (1984-2025).

{{ config(materialized='table') }}

with days as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('1980-01-01' as date)",
        end_date="cast('2031-01-01' as date)"
    ) }}

)

select cast(date_day as date) as date_day
from days
