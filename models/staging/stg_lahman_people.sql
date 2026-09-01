-- Lahman People, narrowed to the identity bridge the semantic layer needs:
-- retroID is what joins Lahman careers to Retrosheet play-by-play ids.
-- Rows without a retroID can never match a play, so they stay at source.

with source as (

    select * from {{ source('lahman', 'people') }}

),

renamed as (

    select
        playerID                                            as player_id,
        retroID                                             as retro_id,
        trim(concat(coalesce(nameFirst, ''), ' ', nameLast)) as player_name,
        debut,
        finalGame                                           as final_game

    from source
    where retroID is not null

)

select * from renamed
