-- Every play marked was_attended = true in fct_plays must trace to a game
-- marked was_attended = true in fct_games. Catches drift between the play
-- and game denorm — if fct_games's filter changes but fct_plays's join lags,
-- this surfaces immediately. Returns 0 rows when healthy.
select
    p.game_id,
    p.event_id,
    p.was_attended as play_was_attended,
    g.was_attended as game_was_attended
from {{ ref('fct_plays') }} p
left join {{ ref('fct_games') }} g on p.game_id = g.game_id
where p.was_attended = true
  and coalesce(g.was_attended, false) = false
