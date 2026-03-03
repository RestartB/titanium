-- Create "spotify_tokens" table
CREATE TABLE "spotify_tokens" (
  "token" character varying NOT NULL,
  "time_added" timestamp NOT NULL DEFAULT now(),
  "expires_in" integer NOT NULL,
  PRIMARY KEY ("token")
);
