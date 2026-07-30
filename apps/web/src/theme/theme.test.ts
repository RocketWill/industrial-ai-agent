import { describe, expect, it } from "vitest";
import { colors } from "./colors";
import { antdTheme } from "./theme";

describe("Dithered dark theme", () => {
  it("exposes the approved semantic palette", () => {
    expect(colors.bgBase).toBe("#0D1230");
    expect(colors.bgContainer).toBe("#0B1028");
    expect(colors.bgElevated).toBe("#0B1739");
    expect(colors.primary).toBe("#0D46F4");
    expect(colors.accent).toBe("#C23CE4");
    expect(colors.textPrimary).toBe("#E8EBFF");
  });

  it("uses dark algorithm and shared component tokens", () => {
    expect(antdTheme.algorithm).toBeDefined();
    expect(antdTheme.token?.colorBgBase).toBe(colors.bgBase);
    expect(antdTheme.token?.colorTextBase).toBe(colors.textPrimary);
    expect(antdTheme.components?.Button?.colorPrimary).toBe(colors.primary);
    expect(antdTheme.components?.Input?.colorBgContainer).toBe(colors.fillAlter);
  });
});
