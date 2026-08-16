-- One row per canonical attendee. The roster seed is the spine, so a name that is
-- registered but not yet in any game still gets a dimension row (games_attended = 0)
-- rather than vanishing.
--
-- games_attended / first_game_date / last_game_date are pre-computed here, following
-- the same reasoning as fct_games' derived columns: these three answer most of what
-- gets asked of this dimension ("who have I seen the most games with", "when did we
-- start going"), and recomputing them on every read is waste.
--
-- attendee_type is what lets a consumer separate real people from the group and
-- placeholder rows without maintaining a hardcoded exclusion list:
--   person   a named individual
--   group    a real answer that isn't one person ('Peeps', 'College Friends')
--   self     Wax alone — 'solo'. He is on all 178 games, so he is never listed as a
--            companion; the token exists so a solo game is distinguishable from an
--            unfilled one.
--   unknown  he was there with someone and cannot recall who. An answer, not a blank.

with roster as (

    select * from {{ ref('stg_attendee_roster') }}

),

appearances as (

    select
        ga.attendee_name,
        count(*)          as games_attended,
        min(g.game_date)  as first_game_date,
        max(g.game_date)  as last_game_date

    from {{ ref('stg_game_attendees') }} as ga
    inner join {{ ref('stg_attended_games') }} as g
        on ga.wax_game_id = g.wax_game_id
    group by ga.attendee_name

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['roster.attendee_name']) }} as attendee_key,
        roster.attendee_name,
        roster.attendee_type,
        roster.real_name,

        -- roster is the spine, so an unused registry entry reads 0, not NULL
        coalesce(appearances.games_attended, 0) as games_attended,
        appearances.first_game_date,
        appearances.last_game_date,

        roster.attendee_type = 'person'          as is_person

    from roster
    left join appearances
        on roster.attendee_name = appearances.attendee_name

)

select * from final
