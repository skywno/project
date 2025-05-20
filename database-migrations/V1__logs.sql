CREATE EXTENSION HSTORE;

CREATE TABLE logs (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  data hstore);

INSERT INTO logs (data) VALUES (
  'ticket_id => 1234567890,
  user_id => 1234567890,
  group_id => 1234567890,
  target_type => rag,
  task => "do something"'
);

