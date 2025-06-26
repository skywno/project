CREATE TABLE event_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL, -- 'request' or 'response'
    ticket_id BIGINT NOT NULL, -- Essential for linking requests and responses
    timestamp TIMESTAMPTZ DEFAULT NOW(), -- When the log entry was created in the DB
    data JSONB NOT NULL -- The flexible payload for request/response details
);

-- Optional: Add a B-tree index on ticket_id for faster lookups
CREATE INDEX idx_event_logs_ticket_id ON event_logs (ticket_id);
