-- Unpivots the flat attendee_1..4 columns into one row per game-person.
--
-- The seed is a faithful mirror of baseball-attendees.csv, which stays wide and
-- hand-editable on purpose (a human has to be able to fix a row by opening the file).
-- The grain change belongs here, not in the file — and it removes the hard cap of
-- four attendees per game: widen the CSV and this model follows without a rewrite.

with source as (

    select * from {{ ref('wax_game_attendees') }}

),

unpivoted as (

    {% for n in range(1, 5) %}
    select
        wax_game_id,
        trim(attendee_{{ n }})  as attendee_name,
        'attendee_{{ n }}'      as source_column,
        {{ n }}                 as source_position
    from source
    where attendee_{{ n }} is not null
      and trim(attendee_{{ n }}) != ''
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

)

select * from unpivoted
