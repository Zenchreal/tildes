-- Copyright (c) 2020 Tildes contributors <code@tildes.net>
-- SPDX-License-Identifier: AGPL-3.0-or-later

create or replace function scraper_results_events_trigger() returns trigger as $$
declare
    affected_row record := coalesce(NEW, OLD);
    stream_name_pieces text[] := array[TG_TABLE_NAME, lower(TG_OP)]::text[] || TG_ARGV;

    -- in general, only the below declaration of payload_fields should be edited
    payload_fields text[] := array[
        'result_id', affected_row.result_id
    ]::text[];
begin
    perform add_to_event_stream(stream_name_pieces, payload_fields);

    return null;
end;
$$ language plpgsql;

create trigger scraper_results_events_insert_delete
    after insert or delete on scraper_results
    for each row
    execute function scraper_results_events_trigger();
