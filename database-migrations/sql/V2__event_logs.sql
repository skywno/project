CREATE TABLE event_logs (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL, -- 'request' or 'response'
    ticket_id BIGINT NOT NULL, -- Essential for linking requests and responses
    user_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(), -- When the log entry was created in the DB
    data JSONB NOT NULL -- The flexible payload for request/response details
);

-- Optional: Add a B-tree index on ticket_id for faster lookups
CREATE INDEX idx_event_logs_ticket_id ON event_logs (ticket_id);
