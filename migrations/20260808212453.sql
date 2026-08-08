-- Remove rep rows whose server rep settings no longer exist
DELETE FROM "user_rep" AS ur
WHERE NOT EXISTS (
  SELECT 1
  FROM "guild_rep_settings" AS grs
  WHERE grs."guild_id" = ur."guild_id"
);
-- Remove history whose target rep row no longer exists
DELETE FROM "rep_add_history" AS rah
WHERE NOT EXISTS (
  SELECT 1
  FROM "user_rep" AS ur
  WHERE ur."user_id" = rah."target_id"
    AND ur."guild_id" = rah."guild_id"
);
-- Modify "user_rep" table
ALTER TABLE "user_rep" ADD CONSTRAINT "user_rep_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_rep_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "rep_add_history" table
ALTER TABLE "rep_add_history" ADD CONSTRAINT "rep_add_history_target_id_guild_id_fkey" FOREIGN KEY ("target_id", "guild_id") REFERENCES "user_rep" ("user_id", "guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
