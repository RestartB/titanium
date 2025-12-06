-- Modify "bouncer_actions" table
ALTER TABLE "bouncer_actions" DROP CONSTRAINT "bouncer_actions_rule_id_fkey", ADD CONSTRAINT "bouncer_actions_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "bouncer_rules" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "bouncer_criteria" table
ALTER TABLE "bouncer_criteria" DROP CONSTRAINT "bouncer_criteria_rule_id_fkey", ADD CONSTRAINT "bouncer_criteria_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "bouncer_rules" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
