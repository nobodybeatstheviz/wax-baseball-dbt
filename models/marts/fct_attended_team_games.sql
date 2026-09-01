-- One row per attended game x participating team (178 games -> 356 rows).
-- The unpivot that makes win rate a governed metric with team as a DIMENSION
-- rather than a hardcoded constant (ruled 2026-08-31): "how did the Yankees do
-- with me there" is a query-time filter, never part of the definition.
--
-- team_won derives from fct_games.winning_team_id, which is computed from
-- Retrosheet scores — the authoritative side, untouched by the known
-- venue/home/away swap in the raw attended_games rows for the 2000 Subway Series.

with games as (

    select * from {{ ref('fct_games') }}
    where was_attended = true

),

home_side as (

    select
        game_id,
        wax_game_id,
        game_date,
        game_type_wax,
        venue_wax,
        is_yankees_game,
        home_team_id_retro      as team_id,
        away_team_id_retro      as opponent_team_id,
        true                    as is_home,
        home_score              as team_score,
        away_score              as opponent_score,
        winning_team_id
    from games

),

away_side as (

    select
        game_id,
        wax_game_id,
        game_date,
        game_type_wax,
        venue_wax,
        is_yankees_game,
        away_team_id_retro      as team_id,
        home_team_id_retro      as opponent_team_id,
        false                   as is_home,
        away_score              as team_score,
        home_score              as opponent_score,
        winning_team_id
    from games

),

unioned as (

    select * from home_side
    union all
    select * from away_side

),

final as (

    select
        *,

        -- ties/suspended games have no winning_team_id; they stay in the table
        -- (they were attended) but drop out of the win-rate denominator.
        (winning_team_id is not null)                    as is_decided,
        coalesce(team_id = winning_team_id, false)       as team_won

    from unioned

)

select * from final
