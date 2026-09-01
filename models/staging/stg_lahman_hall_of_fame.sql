-- Lahman HallOfFame, filtered to actual inductions.
-- The source is ballot history — one row per player per ballot year — but the
-- semantic layer only asks "is this player in the Hall"; the ballot story stays
-- at source. yearid is lowercase in the 2025 drop, and BigQuery autodetect
-- typed the Y/N inducted column as BOOL (both source quirks, kept upstream).

with source as (

    select * from {{ source('lahman', 'hall_of_fame') }}

),

inducted as (

    select
        playerID    as player_id,
        yearid      as induction_year,
        category

    from source
    where inducted

)

select * from inducted
