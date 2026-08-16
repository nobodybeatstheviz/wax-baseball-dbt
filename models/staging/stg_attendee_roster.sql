-- Thin staging model over the hand-maintained canonical name registry.
-- No joins, no derivations — just typing and empty-string-to-NULL.

with source as (

    select * from {{ ref('attendee_roster') }}

),

renamed as (

    select
        trim(attendee_name)         as attendee_name,
        trim(attendee_type)         as attendee_type,
        nullif(trim(real_name), '') as real_name

    from source

)

select * from renamed
