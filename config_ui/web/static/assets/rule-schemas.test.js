import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  emptyRule,
  migrateRuleType,
  migrationDataLoss,
  validateRule,
  RULE_TYPES,
} from "./rule-schemas.js";

describe("emptyRule", () => {
  for (const type of RULE_TYPES) {
    it(`seeds ${type}`, () => {
      const rule = emptyRule(type);
      assert.equal(rule.type, type);
      assert.equal(rule.muted, false);
      const v = validateRule(rule);
      assert.equal(v.ok, false, `${type} should start incomplete until filled`);
    });
  }

  it("scale_follow has expected keys", () => {
    const rule = emptyRule("scale_follow");
    assert.ok("target" in rule && "source" in rule && "factor" in rule);
  });

  it("cross_proportion_clamp has nested blocks", () => {
    const rule = emptyRule("cross_proportion_clamp");
    assert.ok(rule.if && rule.and && rule.then_clamp);
  });

  it("winner_take_all seeds two params", () => {
    const rule = emptyRule("winner_take_all");
    assert.equal(rule.params.length, 2);
  });
});

describe("migrateRuleType", () => {
  it("drops scale_follow fields when switching to mutual_dampen", () => {
    const rule = emptyRule("scale_follow");
    rule.target = "A";
    rule.source = "B";
    const next = migrateRuleType(rule, "mutual_dampen");
    assert.equal(next.type, "mutual_dampen");
    assert.ok(!("source" in next));
    assert.ok(Array.isArray(next.params));
  });

  it("reports data loss", () => {
    const rule = emptyRule("scale_follow");
    rule.source = "JawBind.location.y";
    const lost = migrationDataLoss(rule, "winner_take_all");
    assert.ok(lost.includes("source"));
  });
});

describe("validateRule", () => {
  it("passes complete scale_follow", () => {
    const rule = {
      type: "scale_follow",
      target: "MouthBind.location.y",
      source: "JawBind.location.y",
      factor: 0.5,
    };
    assert.equal(validateRule(rule).ok, true);
  });

  it("requires min or max for conditional_clamp", () => {
    const rule = emptyRule("conditional_clamp");
    rule.target = "X";
    rule.condition = { param: "Y", above: 1 };
    const v = validateRule(rule);
    assert.ok(v.missing.some((m) => m.includes("Min or max")));
  });
});
