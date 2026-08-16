-- 'solo' means Wax went alone, so it can never share a game with another attendee.
-- normalize_attendees.py enforces this on write (it drops 'solo' from any row that
-- also names someone); this asserts it stayed true after the round trip through the
-- seed and the unpivot.
--
-- The failure this guards against is subtle and one-directional: a hand-edit that
-- adds a companion to a solo game without clearing the token leaves a game that is
-- simultaneously solo and not. Returns 0 rows when healthy.
with solo_games as (

    select wax_game_id
    from {{ ref('fct_game_attendee') }}
    where attendee_type = 'self'

)

select
    fa.wax_game_id,
    count(*) as attendee_count

from {{ ref('fct_game_attendee') }} as fa
inner join solo_games
    on fa.wax_game_id = solo_games.wax_game_id

group by fa.wax_game_id
having count(*) > 1
