-- Every one of Wax's attended games must produce at least one row in
-- fct_game_attendee. This is the model-layer enforcement of the rule the flat file
-- follows by hand: an attendee answer is never blank. A game he went to alone
-- carries 'solo'; a game he cannot recall carries 'unknown'. Neither is empty.
--
-- Catches: a cleared cell in the CSV, a name dropped by a failed roster join, and
-- an unpivot that silently lost a column.
-- Returns 0 rows when healthy.
select
    g.wax_game_id,
    g.game_date

from {{ ref('stg_attended_games') }} as g
left join {{ ref('fct_game_attendee') }} as fa
    on g.wax_game_id = fa.wax_game_id

where fa.wax_game_id is null
