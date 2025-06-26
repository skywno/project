CREATE EXTENSION HSTORE;

CREATE TYPE STATUS AS ENUM ('in_progress', 'completed');

CREATE TABLE logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Unique identifer for a specific user request
  ticket_id TEXT NOT NULL,
  
  -- Identifer for a specific user who made the request, it could be a reference, but text for simplicity
  user_id TEXT,
  
  -- Identifer for a specific group, it could be a reference, but text for simplicity
  group_id TEXT,
  
  -- Service target_type
  target_type TEXT,

  -- Request status
  current_status STATUS,

  -- Timestamp when the user's request was initially submitted to the service
  request_submission_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Timestamp when the first chunk/token of the response was sent
  processing_start_time TIMESTAMPTZ,

  -- Timestamp when service was fullly completed
  processing_end_time TIMESTAMPTZ,

  -- Timestamp when service updated last time
  processing_last_update_time TIMESTAMPTZ,

  -- Time when the user receives the final completed response
  response_completion_time TIMESTAMPTZ,

  -- Response from service
  message TEXT
);
