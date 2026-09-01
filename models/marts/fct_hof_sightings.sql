-- One row per Hall of Famer Wax has seen play — the four-way join made material:
-- attended games (spreadsheet) -> plays (Retrosheet) -> People.retroID (Lahman
-- identity bridge) -> HallOfFame inductions (Lahman). Materialized as a mart so
-- every engine's semantic layer defines the same trivial count over the same
-- ported table, instead of each vendor re-deriving a multi-hop join.
--
-- "Seen play" = appeared as batter or pitcher in a play of an attended game.
-- Category filter: players inducted AS players (managers/umpires/executives
-- excluded — Wax saw them work, not play).

with plays as (

    select * from {{ ref('fct_plays') }}
    where was_attended = true

),

appearances as (

    select game_id, game_date, batter_id as retro_id, 'batter' as role
    from plays
    where batter_id is not null

    union all

    select game_id, game_date, pitcher_id as retro_id, 'pitcher' as role
    from plays
    where pitcher_id is not null

),

people as (

    select * from {{ ref('stg_lahman_people') }}

),

hof_players as (

    select * from {{ ref('stg_lahman_hall_of_fame') }}
    where category = 'Player'

),

joined as (

    select
        people.player_id,
        people.player_name,
        people.retro_id,
        hof_players.induction_year,
        appearances.role,
        appearances.game_id,
        appearances.game_date

    from appearances
    inner join people on appearances.retro_id = people.retro_id
    inner join hof_players on people.player_id = hof_players.player_id

),

final as (

    select
        player_id,
        any_value(player_name)        as player_name,
        any_value(retro_id)           as retro_id,
        any_value(induction_year)     as induction_year,
        count(distinct game_id)       as games_seen,
        count(*)                      as plays_seen,
        min(game_date)                as first_seen_date,
        max(game_date)                as last_seen_date,
        logical_or(role = 'batter')   as seen_batting,
        logical_or(role = 'pitcher')  as seen_pitching

    from joined
    group by player_id

)

select * from final
