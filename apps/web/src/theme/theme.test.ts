import { describe, expect, it } from "vitest";
import { colors } from "./colors";
import { antdTheme, layoutTokens, spacing } from "./theme";

describe("Dithered dark theme", () => {
  it("exposes the approved semantic palette", () => {
    expect(colors.bgBase).toBe("#0B0F14");
    expect(colors.bgContainer).toBe("#121922");
    expect(colors.bgElevated).toBe("#18212C");
    expect(colors.primary).toBe("#5B8CFF");
    expect(colors.accent).toBe("#37C6D0");
    expect(colors.textPrimary).toBe("#E8EEF6");
  });

  it("uses dark algorithm and shared component tokens", () => {
    expect(antdTheme.algorithm).toBeDefined();
    expect(antdTheme.token?.colorBgBase).toBe(colors.bgBase);
    expect(antdTheme.token?.colorTextBase).toBe(colors.textPrimary);
    expect(antdTheme.components?.Button?.colorPrimary).toBe(colors.primary);
    expect(antdTheme.components?.Input?.colorBgContainer).toBe(colors.input);
  });

  it("exports the workbench spacing and layout scale", () => {
    expect(layoutTokens.sidebarWidth).toBe(280);
    expect(layoutTokens.workspaceBarHeight).toBe(56);
    expect(layoutTokens.breakpointMobile).toBe(768);
    expect(layoutTokens.conversationItemPaddingInline).toBe(16);
    expect(layoutTokens.messageItemPaddingInline).toBe(24);
    expect(spacing.xxl).toBe(24);
  });
});
