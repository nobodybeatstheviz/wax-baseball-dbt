with retro as (

    select * from {{ ref('stg_retrosheet_games') }}

),

wax as (

    select * from {{ ref('stg_attended_games') }}

),

joined as (

    select
        -- Retrosheet is the spine (game grain over the full filtered substrate).
        -- Wax columns join via LEFT so non-attended games persist when the
        -- filter_to_attended var is flipped off; under the default filter,
        -- every row in retro is an attended game and wax cols are always populated.
        retro.game_id,
        retro.game_date,

        -- Retrosheet's matching identifiers
        retro.home_team_id                  as home_team_id_retro,
        retro.away_team_id                  as away_team_id_retro,
        retro.park_id,

        -- Wax's identifying columns (NULL for non-attended games)
        wax.wax_game_id,
        wax.game_type                       as game_type_wax,
        wax.venue                           as venue_wax,
        wax.city,
        wax.state,
        wax.home_team_name,
        wax.away_team_name,
        wax.home_team_id                    as home_team_id_wax,
        wax.away_team_id                    as away_team_id_wax,

        -- The actual game facts from Retrosheet
        retro.home_score,
        retro.away_score,
        retro.innings_played,
        retro.game_length_minutes,
        retro.day_of_week,
        retro.start_time,
        retro.day_night_code,

        -- Flags
        retro.is_doubleheader,
        retro.is_allstar,
        retro.game_type_code                as game_type_retro,

        -- Weather + atmosphere
        retro.temperature_f,
        retro.wind_direction_code,
        retro.wind_speed_mph,
        retro.precipitation_code,
        retro.sky_code,
        retro.attendance,
        retro.home_plate_umpire,

        -- Decision pitchers
        retro.winning_pitcher_id,
        retro.losing_pitcher_id,
        retro.save_pitcher_id

    from retro
    left join wax on retro.game_id = wax.wax_game_id

),

with_derived as (

    select
        *,

        -- was Wax there? Derived from the LEFT JOIN, not a separate lookup.
        (wax_game_id is not null) as was_attended,

        -- who won
        case
            when home_score > away_score then home_team_id_retro
            when away_score > home_score then away_team_id_retro
        end as winning_team_id,

        -- score margin
        abs(home_score - away_score) as score_margin,

        -- was it a Yankees game (home or away)
        (home_team_id_retro = 'NYA' or away_team_id_retro = 'NYA') as is_yankees_game,

        -- did the home team win
        (home_score > away_score) as home_team_won

    from joined

)

select * from with_derived
