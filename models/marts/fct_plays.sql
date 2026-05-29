with plays as (

    select * from {{ ref('stg_retrosheet_events') }}

),

games as (

    select
        game_id,
        game_date,
        was_attended,
        home_team_id_retro,
        away_team_id_retro,
        park_id,
        venue_wax,
        is_yankees_game
    from {{ ref('fct_games') }}

),

joined as (

    select
        -- composite primary key
        plays.game_id,
        plays.event_id,

        -- denormalized game context (the 80% filter surface)
        games.game_date,
        games.was_attended,
        games.home_team_id_retro,
        games.away_team_id_retro,
        games.park_id,
        games.venue_wax,
        games.is_yankees_game,

        -- inning state
        plays.inning,
        plays.is_bottom_half_inning,
        plays.outs_before,
        plays.outs_on_play,

        -- pitch / count state
        plays.balls,
        plays.strikes,
        plays.pitch_sequence,
        plays.count_text,

        -- batter / pitcher
        plays.batter_id,
        plays.pitcher_id,
        plays.batter_hand,
        plays.pitcher_hand,
        plays.batter_lineup_slot,

        -- event classification (event_code FK to dim_event_code)
        plays.event_code,
        plays.event_text,
        plays.hit_code,
        plays.runs_on_play,
        plays.rbi,
        plays.batted_ball_type,
        plays.batted_ball_location,

        -- score state
        plays.away_score_before,
        plays.home_score_before,

        -- flags
        plays.is_leadoff,
        plays.is_pinch_hitter,
        plays.is_double_play,
        plays.is_triple_play

    from plays
    left join games on plays.game_id = games.game_id

)

select * from joined
