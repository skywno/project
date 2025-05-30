FROM flyway/flyway:11.4-alpine

# Assuming we're building the image inside the `database-migrations` -folder
COPY sql/ /flyway/sql/

# Use shell form for entrypoint to get access to env variables
ENTRYPOINT ./flyway migrate -user=$FLYWAY_USER -password=$FLYWAY_PASSWORD -url="jdbc:postgresql://${POSTGRES_SERVICE_HOST}:${POSTGRES_SERVICE_PORT}/${POSTGRES_DB}"