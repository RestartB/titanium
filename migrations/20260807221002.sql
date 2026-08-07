-- Modify "automod_criteria" table
ALTER TABLE "automod_criteria" ALTER COLUMN "match_whole_word" SET DEFAULT true;
-- Modify "bouncer_criteria" table
ALTER TABLE "bouncer_criteria" ALTER COLUMN "match_whole_word" SET DEFAULT true;
