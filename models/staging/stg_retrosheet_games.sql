with source as (

    select * from {{ source('retrosheet', 'retrosheet_games') }}
    where GAME_ID in (select wax_game_id from {{ ref('stg_attended_games') }})

),

renamed as (

    select
        -- identifiers + join key
        GAME_ID                  as game_id,
        GAME_DATE                as game_date,
        GAME_TYPE                as game_type_code,

        -- who played, who won
        HOME_TEAM_ID             as home_team_id,
        AWAY_TEAM_ID             as away_team_id,
        HOME_SCORE_CT            as home_score,
        AWAY_SCORE_CT            as away_score,

        -- context
        PARK_ID                  as park_id,
        DAYOFWEEK_GAME_DT        as day_of_week,
        START_TIME_GAME_DT       as start_time,
        DAYNIGHT_PARK_CD         as day_night_code,
        MINUTES_GAME_CT          as game_length_minutes,

        -- flags
        IS_GAME_DOUBLEHEADER     as is_doubleheader,
        IS_ALLSTAR_MLB           as is_allstar,
        INN_CT                   as innings_played,

        -- weather + conditions
        TEMP_PARK_CT             as temperature_f,
        WIND_DIRECTION_PARK_CD   as wind_direction_code,
        WIND_SPEED_PARK_DM       as wind_speed_mph,
        PRECIP_PARK_CD           as precipitation_code,
        SKY_PARK_CD              as sky_code,

        -- attendance
        ATTEND_PARK_CT           as attendance,

        -- home plate umpire (one fans actually notice)
        HOMEPLATE_UMP_TX         as home_plate_umpire,

        -- game-decision pitchers (the Mariano Rivera question, etc.)
        WIN_PIT_ID               as winning_pitcher_id,
        LOSE_PIT_ID              as losing_pitcher_id,
        SAVE_PIT_ID              as save_pitcher_id

    from source

)

select * from renamed
