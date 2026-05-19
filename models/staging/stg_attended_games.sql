with source as (

    select * from {{ source('wax', 'attended_games') }}

),

renamed as (

    select
        WAX_GAME_ID    as wax_game_id,
        Date           as game_date,
        Away_Team      as away_team_name,
        Away_Team_ID   as away_team_id,
        Home_Team      as home_team_name,
        Home_Team_ID   as home_team_id,
        Venue          as venue,
        City           as city,
        State          as state,
        Game_Type      as game_type

    from source

)

select * from renamed
