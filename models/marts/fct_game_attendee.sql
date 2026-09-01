-- One row per game x attendee. The bridge that attendee_1..4 could never be.
--
-- Denormalizes game_date, attendee_type and is_yankees_game for the 80% query path,
-- matching fct_plays' convention — re-join to fct_games for anything heavier.
--
-- source_column / source_position carry provenance back to the exact cell in
-- baseball-attendees.csv. When a row looks wrong the answer is "open the file and
-- look at attendee_3", not a spelunk through the model DAG.

with game_attendees as (

    select * from {{ ref('stg_game_attendees') }}

),

attendees as (

    select * from {{ ref('dim_attendee') }}

),

games as (

    select * from {{ ref('fct_games') }}
    where was_attended = true

),

final as (

    select
        -- explicit grain key: (game, attendee). Downstream systems that demand a
        -- single-column primary key (Data 360 DLOs) get one instead of inventing one.
        game_attendees.wax_game_id || '-' || attendees.attendee_key as game_attendee_key,
        game_attendees.wax_game_id,
        attendees.attendee_key,
        attendees.attendee_name,
        attendees.attendee_type,

        games.game_date,
        games.is_yankees_game,
        games.game_type_wax,

        game_attendees.source_column,
        game_attendees.source_position

    from game_attendees

    -- inner: the roster guardrail in sync_attendees_to_dbt.py already fails the sync
    -- on an unregistered name, so a miss here means the seeds drifted out of step.
    -- The relationships test on attendee_key is what catches that.
    inner join attendees
        on game_attendees.attendee_name = attendees.attendee_name

    inner join games
        on game_attendees.wax_game_id = games.wax_game_id

)

select * from final
