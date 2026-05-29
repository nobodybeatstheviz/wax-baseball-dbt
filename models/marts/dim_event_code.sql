with source as (

    select * from {{ ref('retrosheet_event_codes') }}

)

select
    event_code,
    event_name,
    event_category,
    is_batter_event
from source
