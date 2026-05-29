with source as (

    select * from {{ source('retrosheet', 'retrosheet_events') }}
    {% if var('filter_to_attended', true) %}
    where GAME_ID in (select wax_game_id from {{ ref('stg_attended_games') }})
    {% endif %}

),

renamed as (

    select
        -- identifiers + join keys
        GAME_ID                   as game_id,
        EVENT_ID                  as event_id,

        -- inning state
        INN_CT                    as inning,
        (BAT_HOME_ID = 1)         as is_bottom_half_inning,
        OUTS_CT                   as outs_before,
        EVENT_OUTS_CT             as outs_on_play,

        -- pitch / count state
        BALLS_CT                  as balls,
        STRIKES_CT                as strikes,
        PITCH_SEQ_TX              as pitch_sequence,
        COUNT_TX                  as count_text,

        -- batter / pitcher
        BAT_ID                    as batter_id,
        PIT_ID                    as pitcher_id,
        BAT_HAND_CD               as batter_hand,
        PIT_HAND_CD               as pitcher_hand,
        BAT_LINEUP_ID             as batter_lineup_slot,

        -- event classification
        EVENT_CD                  as event_code,
        EVENT_TX                  as event_text,
        H_CD                      as hit_code,
        EVENT_RUNS_CT             as runs_on_play,
        RBI_CT                    as rbi,
        BATTEDBALL_CD             as batted_ball_type,
        BATTEDBALL_LOC_TX         as batted_ball_location,

        -- score state at start of play
        AWAY_SCORE_CT             as away_score_before,
        HOME_SCORE_CT             as home_score_before,

        -- flags (T/F strings at source → booleans)
        (LEADOFF_FL = 'T')        as is_leadoff,
        (PH_FL = 'T')             as is_pinch_hitter,
        (DP_FL = 'T')             as is_double_play,
        (TP_FL = 'T')             as is_triple_play

    from source

)

select * from renamed
